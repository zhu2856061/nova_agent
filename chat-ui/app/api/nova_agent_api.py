import json
import logging
import uuid

import httpx
import requests

logger = logging.getLogger(__name__)

AGENT_BACKEND_URL = {
    "llm": "http://0.0.0.0:2021/agent/chat",
    "memorizer": "http://0.0.0.0:2021/agent/memorizer",
    "themeslicer": "http://0.0.0.0:2021/agent/themeslicer",
    "researcher": "http://0.0.0.0:2021/agent/researcher",
    "wechat_researcher": "http://0.0.0.0:2021/agent/wechat_researcher",
    "deepresearcher": "http://0.0.0.0:2021/agent/deepresearcher",
    "ainovel_extract_setting": "http://0.0.0.0:2021/agent/ainovel_extract_setting",
    "ainovel_core_seed": "http://0.0.0.0:2021/agent/ainovel_core_seed",
    "ainovel_world_building": "http://0.0.0.0:2021/agent/ainovel_world_building",
    "ainovel_character_dynamics": "http://0.0.0.0:2021/agent/ainovel_character_dynamics",
    "ainovel_plot_arch": "http://0.0.0.0:2021/agent/ainovel_plot_arch",
    "ainovel_chapter_blueprint": "http://0.0.0.0:2021/agent/ainovel_chapter_blueprint",
    "ainovel_build_architecture": "http://0.0.0.0:2021/agent/ainovel_build_architecture",
    "ainovel_architect": "http://0.0.0.0:2021/agent/ainovel_architect",
    "ainovel_chapter": "http://0.0.0.0:2021/agent/ainovel_chapter",
    "ainovel": "http://0.0.0.0:2021/agent/ainovel",
    "human_in_loop": "http://0.0.0.0:2021/agent/human_in_loop",
}


async def get_nova_agent_api(url_name: str, trace_id: str, state: dict, context: dict):
    """
    发送请求到后端并获取流式响应

    Args:
        url: 请求的URL
        trace_id: 请求的trace_id
        state: 状态数据
        context: 上下文数据

    Yields:
        流式返回的响应内容片段
    """
    trace_id = trace_id or str(uuid.uuid4())

    request_data = {"trace_id": trace_id, "context": context, "state": state}

    try:
        url = AGENT_BACKEND_URL[url_name]
        async with httpx.AsyncClient() as client:
            # 发送 POST 请求到 /stream_llm 路由
            async with client.stream(
                "POST", url, json=request_data, timeout=3600.0
            ) as response:
                response.raise_for_status()
                # 检查响应状态码
                if response.status_code != 200:
                    logger.error(f"Error: {response.status_code}")
                    return

                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue  # 跳过空行
                    try:
                        line_data = json.loads(chunk.decode("utf-8"))
                        if line_data.get("code") != 0:
                            yield {
                                "type": "error",
                                "content": line_data.get("err_message"),
                            }
                            return

                        # 提取内容
                        yield extract_event_data(line_data["data"])

                    except json.JSONDecodeError:
                        error_msg = f"❌ 响应格式错误: 无法解析内容: {chunk[:200]}..."
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return
                    except KeyError as e:
                        error_msg = f"❌ 响应结构错误: 缺少必要字段「{str(e)}」"
                        logger.error(f"{error_msg} (trace_id: {trace_id})")
                        yield {"type": "error", "content": error_msg}
                        return

    except requests.exceptions.RequestException as e:
        error_msg = f"❌ 请求失败: {str(e)}（流式连接中断）"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield {"type": "error", "content": error_msg}
        return
    except Exception as e:
        error_msg = f"❌ 流式处理异常: {str(e)}"
        logger.error(f"{error_msg} (trace_id: {trace_id})")
        yield {"type": "error", "content": error_msg}
        return


def extract_event_data(line_data):
    _event = line_data.get("event")
    _data = line_data.get("data")
    if not _event:
        return

    # 系统事件
    if _event == "llm_stream":
        _reasoning_content = _data.get("reasoning_content", "")
        _content = _data.get("content", "")
        # 思考内容
        if _reasoning_content:
            return {"type": "thought", "content": f"{_reasoning_content}"}

        # 回答内容
        if _content:
            return {"type": "answer", "content": f"{_content}"}

    elif _event == "on_chain_start":
        _node_name = _data.get("node_name")
        if _node_name == "LangGraph":
            content = f"\n\n⏳ 【 {_node_name} 】 图开始\n\n"
            return {"type": "system", "content": "\n\n"}

        content = f"\n\n⏳ 【 {_node_name} 】 节点开始\n\n"
        return {"type": "system", "content": content}

    elif _event == "on_chain_end":
        _node_name = _data.get("node_name")
        _output = _data.get("output")
        if _node_name == "LangGraph":
            content = f"\n\n✅ 【 {_node_name} 】 图结束 \n\n"
        else:
            content = f"\n\n✅ 【 {_node_name} 】 节点结束 \n\n"

        # 只关注最终LangGGraph输出
        if _output and _node_name == "LangGraph":
            if isinstance(_output, dict):
                if _output["code"] != 0:
                    return {"type": "error", "content": _output["err_message"]}
                _data = _output.get("data")
                content += f"{_data}\n\n"

        return {"type": "system", "content": content}

    elif _event == "on_tool_start":
        _node_name = _data.get("node_name")
        _input = _data.get("input")
        content = f"\n\n🛠️ 【 {_node_name} 】 开始调用工具 \n\n"
        if _input:
            _input = str(_input)[:200]
            content += f"入参: {_input}\n\n"
            return {"type": "system", "content": content}
        else:
            return {"type": "system", "content": content}

    elif _event == "on_tool_end":
        _node_name = _data.get("node_name")
        _output = _data.get("output")
        content = f"\n\n🛠️ 【 {_node_name} 】 结束调用工具: \n\n"
        if _output:
            _output = str(_output)[:200]
            content += f"出参: {_output}\n\n"
            return {"type": "system", "content": content}
        else:
            return {"type": "system", "content": content}

    elif _event == "on_chat_model_start":
        _node_name = _data.get("node_name")
        content = f"\n\n⏳ 【 {_node_name} 】 LLM模型开始 \n\n"
        return {"type": "system", "content": content}

    elif _event == "on_chat_model_end":
        _node_name = _data.get("node_name")
        _output = _data.get("output")
        content = f"\n\n✅【 {_node_name} 】 LLM模型结束 \n\n"
        if _output:
            _content = _output["content"]
            _reasoning_content = _output["reasoning_content"]
            _tool_calls = _output["tool_calls"]

            if _reasoning_content:
                content += f"ℹ️ 【Think】\n\n{_reasoning_content}\n\n"

            if _content:
                content += f"📘 【Answer】\n\n{_content}\n\n"

            if _tool_calls:
                for _tool_call in _tool_calls:
                    _tool_name = _tool_call["name"]
                    _tool_args = _tool_call["args"]
                    content += f"🛠️ 【Tool: {_tool_name}】\n\n{_tool_args}\n\n"

            return {"type": "system", "content": content}
        else:
            return {"type": "system", "content": content}

    elif _event == "on_chat_model_stream":
        _node_name = _data.get("node_name")
        _output = _data.get("output")

        _reasoning_content = _output.get("reasoning_content", "")
        _content = _output.get("content", "")
        # 思考内容
        if _reasoning_content:
            return {"type": "thought", "content": f"{_reasoning_content}"}

        # 回答内容
        if _content:
            return {"type": "answer", "content": f"{_content}"}

    elif _event == "human_in_loop":
        _node_name = _data.get("node_name")
        _output = _data.get("output")
        return {
            "type": "human_in_loop",
            "content": f"\n\n🐞 【 {_node_name} 】 人工介入：\n\n{_output}\n\n",
        }

    elif _event == "on_parser_end":
        _node_name = _data.get("node_name")
        _output = _data.get("output")
        return {
            "type": "human_in_loop",
            "content": f"\n\n✅ 【 {_node_name} 】 完成：\n\n{_output}\n\n",
        }

    else:
        return
