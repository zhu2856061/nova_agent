# -*- coding: utf-8 -*-
# @Time   : 2025/04/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import json
import logging
import time
import uuid
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from nova import CONF
from nova.graph.agents import research_agent
from nova.graph.configuration import Configuration
from nova.graph.mstate import OverallState
from nova.graph.template import apply_system_prompt_template
from nova.llms import get_llm_by_type
from nova.tools import (
    create_directory_tool,
    handoff_to_planner,
    read_json_tool,
    serp_tool,
    write_file_tool,
    write_json_tool,
)
from nova.utils import repair_json_output, set_color

logger = logging.getLogger(__name__)


def write_to_log(node, response, task_dir, appended=False):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    _tmp = {"current_time": current_time, "node": node, "node_output": response}
    _tmp = json.dumps(_tmp, ensure_ascii=False) + "\n"
    write_file_tool.run(
        {
            "file_path": f"{task_dir}/log.jsonl",
            "text": _tmp,
            "append": appended,
        },
    )


# 🌟
def coordinator_node(
    state: OverallState,
    config: RunnableConfig,
) -> Command[Literal["planner", "__end__"]]:
    """协调员将任务分配给不同的团队，每个团队包含「管理员*1 计划者*0/1 执行者* N」"""
    configurable = Configuration.from_runnable_config(config)
    if configurable.task_id == "":
        configurable.task_id = str(uuid.uuid4())
    _task = configurable.task_id
    _task_dir = CONF["SYSTEM"]["TASK_DIR"] + "/" + _task
    _model_name = configurable.coordinator_model

    def _assemble_prompt():
        """
        组装成提示 system message + user message
        SystemMessage + HumanMessage[question]
        """
        if state["messages"] is None:
            return "__end__"
        system_messages = apply_system_prompt_template("coordinator", state)

        all_messages = system_messages + state["messages"]
        return all_messages

    def _execute_llm(messages):
        """
        执行LLM - 基于LLM的意图识别， 未来有更好的意图识别（采用handoff_to_planner工具承接））
        """
        response = (
            get_llm_by_type(_model_name)
            .bind_tools([handoff_to_planner])
            .invoke(messages)
        )
        response.name = "coordinator"
        write_to_log("coordinator", response.model_dump(), _task_dir)
        return response

    try:
        logger.info(
            set_color(f"📡 >>>>>>> 【{_task}】 - 【Coordinator】 - Activate. ", "pink")
        )
        # 1 创建任务文件夹
        _task_dir = create_directory_tool.run(_task_dir)

        # 2 构建prompt
        messages = _assemble_prompt()
        if messages is None:
            return Command(
                goto="__end__",
                update={
                    "messages": [
                        AIMessage(content="question is None", name="coordinator")
                    ]
                },
            )
        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Coordinator】 - 【assemble_prompt】\n {messages}",
                "pink",
            )
        )

        # 3 执行LLM意图识别
        response = _execute_llm(messages)
        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Coordinator】 - 【execute_llm】\n {response}",
                "pink",
            )
        )

        # 4 决定下一步
        goto = "__end__"
        if len(response.tool_calls) > 0:  # type: ignore
            goto = "planner"

        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Coordinator】 - 【delegating】\n to {goto}",
                "pink",
            )
        )
        if goto == "__end__":
            return Command(
                goto=goto,
                update={
                    "answer": [AIMessage(content=response.content, name="coordinator")]
                },
            )
        else:
            return Command(
                goto=goto, update={"question": state["messages"][-1].content}
            )
    except Exception as e:
        _tmp = f"📡 >>>>>>> 【{_task}】 - 【Coordinator】 - 【Exception】 failed: {e}"
        logger.error(set_color(_tmp, "red"))
        return Command(
            goto="__end__",
            update={"answer": AIMessage(content=_tmp, name="coordinator")},
        )


# 🌟
def planner_node(
    state: OverallState,
    config: RunnableConfig,
) -> Command[Literal["supervisor", "__end__"]]:
    """:计划者
    plan 的内容格式如下：
    {
        "thought": str,
        "title": str,
        "steps": [
            {
                "state": "todo",
                "retry_count": 0,
                "agent_name": "researcher",
                "title": str,
                "description": str
            }
        ]
    }
    """
    configurable = Configuration.from_runnable_config(config)
    _task = configurable.task_id

    _task_dir = CONF["SYSTEM"]["TASK_DIR"] + "/" + _task
    _model_name = configurable.planner_model
    _is_serp_before_planning = configurable.is_serp_before_planning
    _is_deep_thinking_mode = configurable.is_deep_thinking_mode

    def _serp_before_planning(query) -> str:
        """在计划前先进行一次serp搜索"""
        try:
            searched_content = serp_tool.run({"query": query})
            _tmp = []
            for elem in searched_content:
                title = elem["title"]
                content = elem["content"]
                _tmp.append(f"- **title**: {title}, **content**: {content}")
            _tmp = "\n".join(_tmp)
            return _tmp
        except Exception as e:
            logger.error(
                f"search before planning failed : {searched_content}, error: {e}"
            )
            return ""

    def _assemble_prompt():
        """组装成提示
        SystemMessage
        HumanMessage -> Relative Search Results: [serp content] + [question]
        """
        system_messages = apply_system_prompt_template("planner", state)
        question = state.get("question", None)
        if question is None or question == "":
            return None

        tmp = f"Question: {question}"
        if _is_serp_before_planning:
            searched_content = _serp_before_planning(question)
            if searched_content != "":
                tmp = f"\n\n# Relative Search Results:\n\n{searched_content} \n\n {tmp}"

        messages = system_messages + [HumanMessage(content=tmp)]
        return messages

    def _execute_llm(messages):
        """执行LLM"""
        llm = get_llm_by_type(_model_name)
        if _is_deep_thinking_mode:
            llm = get_llm_by_type("REASONING")

        _response = llm.invoke(messages)
        _response.name = "planner"
        write_to_log("planner", _response.model_dump(), _task_dir, appended=True)
        return _response

    def _output_handle(response):
        try:
            _response = repair_json_output(str(response.content))
            # 将数据转换成todo list
            _response = json.loads(_response)
            steps = _response["steps"]
            thought = _response["thought"]
            title = _response["title"]

            # 初始化状态和重试次数
            for i, step in enumerate(steps):
                step["status"] = "TODO"
                step["retry_count"] = 0
            result = {"title": title, "thought": thought, "steps": steps}

            # 将计划写入计划书中
            write_json_tool.run(
                {
                    "file_path": f"{_task_dir}/plan.jsonl",
                    "jsonl": result,
                }
            )
            logger.info(f"<<<<<<< 【{_task}】 plan write in {_task_dir}/plan")
            return result
        except Exception:
            return None

    # -- 计划重试
    try:
        logger.info(
            set_color(f"📡 >>>>>>> 【{_task}】 - 【Planer】 - Activate. ", "pink")
        )
        messages = _assemble_prompt()
        if messages is None:
            return Command(
                goto="__end__",
                update={
                    "messages": [AIMessage(content="question is None", name="planner")]
                },
            )
        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Planer】 - 【assemble_prompt】\n {messages}",
                "pink",
            )
        )
        _response = _execute_llm(messages)
        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Planer】 - 【execute_llm】\n {_response}",
                "pink",
            )
        )
        _response = _output_handle(_response)

        goto = "supervisor"
        if _response is None:
            goto = "__end__"

        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Planer】 - 【output_handle】\n {_response}",
                "pink",
            )
        )
        if goto == "__end__":
            return Command(
                goto=goto,
                update={
                    "answer": [
                        AIMessage(
                            content="planner err: planner not json ", name="coordinator"
                        )
                    ]
                },
            )
        else:
            return Command(
                goto=goto,
                update={"answer": AIMessage(content=[_response], name="planner")},  # type: ignore
            )

    except Exception as e:
        _tmp = f"📡 >>>>>>> 【{_task}】 - 【Planer】 - 【Exception】\n {e}"
        logger.error(set_color(_tmp, "red"))
        return Command(
            goto="__end__",
            update={"answer": AIMessage(content=_tmp, name="planner")},
        )


# 🌟
def supervisor_node(
    state: OverallState,
    config: RunnableConfig,
) -> Command[Literal["researcher", "reporter", "__end__"]]:
    """管理者
        1 拿出计划书，按照计划中的steps逐步执行，下发给具体的agent_name进行执行
        2 获取agent_name的返回结果，并进行验收（需要思考）并更新state字段

    验收结果有三种：
        1 若满意则更新state字段为**DONE**
        2 若不满意且retry_count<设定的阈值则更新state字段为**TODO** , 并要求继续执行该步骤
        3 若不满意且retry_count>设定的阈值更新state字段为**Failed** , 并结束任务
    """
    configurable = Configuration.from_runnable_config(config)
    _task = configurable.task_id
    _task_dir = CONF["SYSTEM"]["TASK_DIR"] + "/" + _task
    _model_name = configurable.supervisor_model
    _retry_limit = configurable.retry_limit

    def _read_plan():
        plan = read_json_tool.run({"file_path": f"{_task_dir}/plan.jsonl"})
        return plan

    def _assemble_prompt(plan, current_task, current_result):
        """组装成提示
        SystemMessage
        HumanMessage -> Plan: [question] + [plan]
        """
        tmp = f"## 整体计划 \n {plan} \n\n ## 当前任务 \n {current_task} \n\n ## 当前任务的结果 \n {current_result} \n"
        system_messages = apply_system_prompt_template("supervisor", state)
        messages = system_messages + [HumanMessage(content=tmp)]

        return messages

    def _execute_llm(messages):
        """执行LLM"""
        response = get_llm_by_type(_model_name).invoke(messages)
        write_to_log("supervisor", response.model_dump(), _task_dir, appended=True)
        return response

    def _output_handle(response):
        _response = response.content
        _response = repair_json_output(str(_response))
        _response = json.loads(_response)
        return _response

    def _acceptance_agent_result(plan, step, result):
        """取出计划并进行更新"""
        _current_step = step
        _current_task = plan.get("steps", [])[_current_step]
        _retry_count = _current_task.get("retry_count", 0)

        _messages = _assemble_prompt(plan, _current_task, result)
        response = _execute_llm(_messages)
        response = _output_handle(response)
        if response["acceptance"] == "ACCEPT":
            _current_task["status"] = "DONE"
            _current_task["result"] = result
            _current_step += 1

        elif response["acceptance"] == "REJECT" and _retry_count < _retry_limit:
            _reason = response.get("reason")
            _current_task["status"] = "TODO"
            _current_task["fail_reason"] = _reason or "Unknown"
            _current_task["retry_count"] = _retry_count + 1

        else:
            _current_task["status"] = "FAIL"
            _current_step = float("inf")

        write_json_tool.invoke(
            {
                "file_path": f"{_task_dir}/plan.jsonl",
                "jsonl": plan,
            }
        )

        return _current_step

    # 基于计划，选择agent
    try:
        logger.info(
            set_color(f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - Activate. ", "pink")
        )

        _answer = state["answer"]
        _plan = _read_plan()
        if _answer.name == "planner" and len(_plan.get("steps", [])) > 0:
            _step = 0
            _step_info = _plan["steps"][_step]
            goto = _step_info.get("agent_name", "__end__")
            logger.info(
                set_color(
                    f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - 【delegating】 to: {goto}",
                    "pink",
                )
            )
            return Command(goto=goto, update={"step": _step})

        elif _answer.name != "planner" and len(_plan.get("steps", [])) > 0:
            _step = state.get("step", 0)
            _answer = state["answer"]

            _step = _acceptance_agent_result(_plan, _step, _answer.content)

            if _step >= len(_plan["steps"]):
                goto = "__end__"
                logger.info(
                    set_color(
                        f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - 【delegating】 to: {goto}",
                        "pink",
                    )
                )
                return Command(goto=goto, update={"messages": [_answer]})

            _step_info = _plan["steps"][_step]
            goto = _step_info.get("agent_name", "__end__")
            logger.info(
                set_color(
                    f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - 【delegating】 to: {goto}",
                    "pink",
                )
            )
            return Command(goto=goto, update={"step": _step})

        else:
            goto = "__end__"
            logger.info(
                set_color(
                    f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - 【delegating】 to: {goto}",
                    "pink",
                )
            )
            return Command(goto=goto)

    except Exception as e:
        _tmp = f"📡 >>>>>>> 【{_task}】 - 【Supervisor】 - 【Exception】 failed: {e}"
        logger.error(set_color(_tmp, "red"))
        return Command(
            goto="__end__",
            update={"answer": AIMessage(content=_tmp, name="supervisor")},
        )


# 🌟
def researcher_node(
    state: OverallState,
    config: RunnableConfig,
) -> Command[Literal["supervisor"]]:
    """Node for the researcher agent that performs research tasks.
    ## 整体计划
    ## 当前任务

    """
    configurable = Configuration.from_runnable_config(config)
    _task = configurable.task_id
    _task_dir = CONF["SYSTEM"]["TASK_DIR"] + "/" + _task
    _step = state.get("step")

    def _assemble_prompt():
        """组装成提示
        HumanMessage -> [整体计划] + [当前任务]
        # - 整体计划
        # - 当前任务
        """
        # 整体计划
        _plan = read_json_tool.run(
            {
                "file_path": f"{_task_dir}/plan.jsonl",
            }
        )

        # 当前任务
        _current_task = _plan["steps"][_step]
        _messages = [
            HumanMessage(
                content=f"## 整体计划 \n {_plan} \n\n ## 当前任务 \n {_current_task}"
            )
        ]

        return {"messages": _messages}

    # 执行LLM
    def _execute_llm(messages):
        _response = research_agent.invoke(messages)

        _tmp = [message.model_dump() for message in _response["messages"]]
        write_to_log("Researcher", _tmp, _task_dir, appended=True)

        return _response

    # 输出处理
    def _output_handle(response):
        _response = response["messages"][-1].content
        _response = repair_json_output(str(_response))
        return _response

    try:
        logger.info(
            set_color(f"📡 >>>>>>> 【{_task}】 - 【Researcher】 - Activate. ", "pink")
        )
        _agent_state = _assemble_prompt()
        _response = _execute_llm(_agent_state)
        _response = _output_handle(_response)

        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Researcher】 - 【delegating】 to: supervisor",
                "pink",
            )
        )
        return Command(
            update={"answer": AIMessage(content=_response, name="researcher")},
            goto="supervisor",
        )

    except Exception as e:
        _tmp = f"📡 >>>>>>> 【{_task}】 - 【Researcher】 - 【Exception】 failed: {e}"
        logger.error(set_color(_tmp, "red"))
        return Command(
            goto="supervisor",
            update={
                "success": False,
                "answer": AIMessage(content=_tmp, name="researcher"),
            },
        )


# 🌟
def reporter_node(
    state: OverallState,
    config: RunnableConfig,
) -> Command[Literal["supervisor"]]:
    """Reporter node that write a final report.
    ## 整体计划
    ## 当前任务
    """
    configurable = Configuration.from_runnable_config(config)
    _task = configurable.task_id
    _task_dir = CONF["SYSTEM"]["TASK_DIR"] + "/" + _task
    logger.info(f">>>>>>> 【{_task}】 ->Reporter<- Activate. ")
    _model_name = configurable.reporter_model

    _step = state.get("step")

    def _assemble_prompt():
        """组装成提示
        SystemMessage
        HumanMessage -> [整体计划] + [当前任务]
        # - 整体计划
        # - 当前任务
        """
        system_messages = apply_system_prompt_template("reporter", state)
        # 整体计划
        _plan = read_json_tool.run(
            {
                "file_path": f"{_task_dir}/plan.jsonl",
            }
        )
        # 当前任务
        _current_task = _plan["steps"][_step]
        _messages = f"## 整体计划 \n {_plan} \n\n ## 当前任务 \n {_current_task}"

        return system_messages + [HumanMessage(content=_messages)]

    # 执行LLM
    def _execute_llm(messages):
        _response = get_llm_by_type(_model_name).invoke(messages)
        write_to_log("reporter", _response.model_dump(), _task_dir, appended=True)
        return _response

    # 输出处理
    def _output_handle(response):
        _response = repair_json_output(str(response.content))
        return _response

    try:
        logger.info(
            set_color(f"📡 >>>>>>> 【{_task}】 - 【Reporter】 - Activate. ", "pink")
        )
        messages = _assemble_prompt()
        _response = _execute_llm(messages)
        _response = _output_handle(_response)

        logger.info(
            set_color(
                f"📡 >>>>>>> 【{_task}】 - 【Reporter】 - 【delegating】 to: supervisor",
                "pink",
            )
        )
        return Command(
            update={
                "answer": AIMessage(content=_response, name="reporter"),
            },
            goto="supervisor",
        )
    except Exception as e:
        _tmp = f"📡 >>>>>>> 【{_task}】 - 【Reporter】 - 【Exception】 failed: {e}"
        logger.error(set_color(_tmp, "red"))
        return Command(
            goto="supervisor",
            update={
                "success": False,
                "answer": AIMessage(content=_tmp, name="reporter"),
            },
        )
