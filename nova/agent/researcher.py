# -*- coding: utf-8 -*-
# @Time   : 2025/09/16 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import logging
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    SystemMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command

from nova.controller.llm_exceptions import (
    LLMContextExceededError,
)
from nova.model.super_agent import SuperContext, SuperState
from nova.node import context_summarize_agent
from nova.provider import get_llms_provider, get_prompts_provider, get_super_agent_hooks
from nova.tools.complete import complete_tool
from nova.tools.web_wechat_search import web_crawl, web_search
from nova.utils.common import (
    get_today_str,
    truncate_if_too_long,
)

# ######################################################################################
# 配置
logger = logging.getLogger(__name__)


# ######################################################################################
# 全局变量


# ######################################################################################
# 函数


def create_researcher_node(
    node_name="researcher",
    *,
    tools=None,
    structured_output=None,
):
    _hook = get_super_agent_hooks()

    async def _before_model_hooks(state: SuperState, runtime: Runtime[SuperContext]):
        # 核心：组装提示词
        _messages = cast(list[AnyMessage], state.get("messages"))

        tmp = {
            "date": get_today_str(),
            "tools_info": get_prompts_provider().get_template("tools", "web_search"),
        }

        _prompt_tamplate = get_prompts_provider().get_template(
            "researcher", "researcher"
        )

        return [
            SystemMessage(
                content=get_prompts_provider().prompt_apply_template(
                    _prompt_tamplate, tmp
                )
            )
        ] + _messages

    @staticmethod
    async def _after_model_hooks(
        response: AIMessage, state: SuperState, runtime: Runtime[SuperContext]
    ):
        _thread_id = runtime.context.get("thread_id", "default")
        logger.info(
            f"_thread_id={_thread_id}, result: {truncate_if_too_long(str(response))}"
        )
        if not isinstance(response, AIMessage):
            return Command(
                update={
                    "code": 1,
                    "err_message": "response type not AIMessage",
                    "messages": [response],
                },
            )
        # 去掉冗余信息
        response.additional_kwargs = {}
        response.response_metadata = {}
        return response

    @_hook.node_with_hooks(node_name="researcher")
    async def _node(state: SuperState, runtime: Runtime[SuperContext]):
        # 获取运行时变量
        _thread_id = runtime.context.get("thread_id", "default")
        _model_name = runtime.context.get("model", "basic")
        _config = runtime.context.get("config", {})

        # 获取状态变量
        _code = state.get("code", 0)
        if _code != 0:
            return Command(goto="__end__")

        _messages = state.get("messages")
        if not _messages:
            return Command(
                update={"code": -1, "data": {"result": "No messages"}},
            )

        if state.get("data") is None:
            _tool_call_iterations = 0
            _max_react_tool_calls = 3
        else:
            _tool_call_iterations = cast(dict, state.get("data")).get(
                "tool_call_iterations", 0
            )
            _max_react_tool_calls = cast(dict, state.get("data")).get(
                "max_react_tool_calls", 3
            )

        # 如果超过次数，则结束
        if _tool_call_iterations + 1 >= _max_react_tool_calls:
            return Command(
                update={
                    "data": {"result": "tool_call_iterations >= max_react_tool_calls"},
                },
            )
        # 这里是如果最后一条消息是工具调用后的返回结果，需要对其长度进行判断，因为网络检索回的信息过长，会导致模型超出token限制
        # if isinstance(_messages[-1], ToolMessage):
        #     _last_message = _messages[-1].content
        #     tool_call_id = _messages[-1].tool_call_id
        #     id = _messages[-1].id

        #     web_search_result = json.loads(cast(str, _last_message))
        #     _summarize_tasks = []
        #     for res in web_search_result:
        #         _summarize_input = SuperState(messages=[HumanMessage(res["text"])])
        #         _summarize_context = SuperContext(**runtime.context)
        #         _summarize_tasks.append(
        #             await webpage_summarize_agent.ainvoke(
        #                 _summarize_input, context=_summarize_context
        #             )
        #         )

        #     _summarize_tasks_output = await asyncio.gather(*_summarize_tasks)

        #     for i, _out in enumerate(_summarize_tasks_output):
        #         _data = _out.get("data")
        #         _summarize_output = ""
        #         if _data:
        #             _summarize_output = _data.get("result")
        #         if _summarize_output:
        #             web_search_result[i]["text"] = _summarize_output
        #         else:
        #             web_search_result[i]["text"] = truncate_if_too_long(
        #                 web_search_result[i]["text"]
        #             )

        #     _messages[-1] = ToolMessage(
        #         json.dumps(web_search_result, ensure_ascii=False),
        #         tool_call_id=tool_call_id,
        #         id=id,
        #     )
        #     state.update({"messages": _messages})

        # 模型执行中
        try:
            # 模型执行前
            response = await _before_model_hooks(state, runtime)

            # 模型执行中
            response = await get_llms_provider().llm_wrap_hooks(
                _thread_id,
                node_name,
                response,
                _model_name,
                tools=tools,
                structured_output=structured_output,
                **_config,  # type: ignore
            )

        except LLMContextExceededError:
            # 这里是如果最后一条消息是工具调用后的返回结果，需要对其长度进行判断，因为网络检索回的信息过长，会导致模型超出token限制
            logger.warning(
                f"_thread_id: {_thread_id}, LLMContextExceededError, truncate the last message"
            )
            response = AIMessage(
                f"_thread_id: {_thread_id}, LLMContextExceededError, truncate the last message"
            )

        # 如果最后返回的是工具，且工具名字为 complete_tool ，则结束
        response = cast(AIMessage, response)
        if hasattr(response, "tool_calls") and response.tool_calls:
            if response.tool_calls[-1]["name"] == "complete_tool":
                return Command(
                    update={
                        "data": {
                            "result": "the last message is complete_tool",
                        },
                    },
                )

        # 模型执行后
        response = await _after_model_hooks(response, state, runtime)
        return Command(
            update={
                "messages": _messages + [response],
                "data": {
                    "result": response.content,
                    "tool_call_iterations": _tool_call_iterations + 1,
                },
            },
        )

    return _node


# 创建路由[ researcher ···> report_node | tools | end]条件边
def create_researcher_route_edges():
    """创建路由[ researcher ···> report_node | tools | end ]条件边"""

    # 4. 定义路由逻辑：判断是否需要调用工具
    def route_edges(state: SuperState, runtime: Runtime[SuperContext]):
        """
        路由规则：
        - 如果最后一条消息包含 tool_calls → 跳转到 tools 节点
        -
        - 否则 → report_node
        """
        # 变量
        _thread_id = runtime.context.get("thread_id", "default")

        _code = state.get("code", 0)
        if _code != 0:
            return "__end__"

        _messages = state.get("messages")
        if not _messages:
            return "__end__"

        logger.info(f"[{_thread_id}]: _messages: {_messages[-1]}")

        if not isinstance(_messages[-1], AIMessage):
            return "report_node"

        last_message = cast(AIMessage, _messages[-1])

        # 检查LLM是否生成了工具调用指令
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"[{_thread_id}]: LLM 生成了工具调用指令: {last_message.tool_calls}"
            )
            return "tools"

        return "report_node"

    return route_edges


def compile_researcher_agent():
    tools = [web_search, web_crawl, complete_tool]

    researcher_node = create_researcher_node(tools=tools)
    tool_node = ToolNode(tools=tools)

    researcher_route_edges = create_researcher_route_edges()

    _agent = StateGraph(SuperState, context_schema=SuperContext)
    _agent.add_node("researcher_node", researcher_node)
    _agent.add_node("report_node", context_summarize_agent)
    _agent.add_node("tools", tool_node)

    _agent.add_edge(START, "researcher_node")
    _agent.add_edge("tools", "researcher_node")

    _agent.add_conditional_edges(
        source="researcher_node",
        path=researcher_route_edges,
        path_map={
            "tools": "tools",
            "report_node": "report_node",
            "__end__": "__end__",  # 结束流程
        },
    )

    checkpointer = InMemorySaver()
    _agent = _agent.compile(checkpointer=checkpointer)
    png_bytes = _agent.get_graph(xray=True).draw_mermaid()
    logger.info(f"researcher_agent: \n\n{png_bytes}")
    return _agent
