import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from src.core.tools.crawl import crawl_tool

# 同步调用
result = crawl_tool.invoke(
    {
        "url": "https://weather.sz.gov.cn/qixiangfuwu/yubaofuwu/jinmingtianqiyubao/index.html",
        "keywords": ["天气"],
    }
)

print(result)
