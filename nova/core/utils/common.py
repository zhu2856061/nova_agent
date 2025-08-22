import logging
import operator
import time
from datetime import datetime
from functools import wraps

from langchain_core.messages import (
    AIMessage,
    MessageLikeRepresentation,
    filter_messages,
)

logger = logging.getLogger(__name__)


# 定义计时装饰器
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()  # 使用高精度计时
        result = func(*args, **kwargs)  # 执行函数
        end_time = time.perf_counter()
        logger.info(f"函数 {func.__name__} 耗时: {end_time - start_time:.4f} 秒")
        return result

    return wrapper


# 设置日志颜色
def set_color(log, color, highlight=True):
    color_set = ["black", "red", "green", "yellow", "blue", "pink", "cyan", "white"]
    try:
        index = color_set.index(color)
    except Exception:
        index = len(color_set) - 1
    prev_log = "\033["
    if highlight:
        prev_log += "1;3"
    else:
        prev_log += "0;3"
    prev_log += str(index) + "m"
    return prev_log + log + "\033[0m"


# 获得当前日期
def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")


# 删除最近一个AI消息
def remove_up_to_last_ai_message(
    messages: list[MessageLikeRepresentation],
) -> list[MessageLikeRepresentation]:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            return messages[:i]
    return messages


# 获取笔记
def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    return [
        tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")
    ]


# 筛选消息
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
