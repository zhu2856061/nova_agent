# -*- coding: utf-8 -*-
# @Time   : 2025/08/01 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
import sys
import time

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

# 设置环境变量
from pydantic import BaseModel

from src.core.llms import get_llm_by_type, with_structured_output


class AnswerWithJustification(BaseModel):
    """An answer to the user question along with justification for the answer."""

    answer: str
    justification: str


llm_instance = get_llm_by_type("BASIC")
try:
    llm_instance = with_structured_output(llm_instance, AnswerWithJustification)
    start = time.time()
    res = llm_instance.invoke(
        "What weighs more a pound of bricks or a pound of feathers"
    )
    end = time.time()
    print(end - start)
    print(res)
except Exception as e:
    print("An error occurred:", e)
