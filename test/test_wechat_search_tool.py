import sys

sys.path.append("..")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"


# result = serp_wechat_tool.invoke(
#     {
#         "query": "大模型",
#         "max_results": 2,
#     }
# )
# print(result)
from nova.tools.wechat_crawler import crawl_wechat_tool
from nova.tools.wechat_serper import serp_wechat_tool

result = crawl_wechat_tool.invoke(
    {
        "url": "https://wx.sogou.com/link?url=dn9a_-gY295K0Rci_xozVXfdMkSQTLW6cwJThYulHEtVjXrGTiVgS3aHmlglMqjZBII-V8GPRWnxM5dY7TUBEFqXa8Fplpd9JDF72Fwv0T0dIE_KOeo9JznZe8s-SllH5D7tVnaOgB1c2gnmH0Rw8TtnchX9p-srwkL_GlC_4Es06xSrFAP24rmJxLvIvFBPIsQ10WXBwsXfc-t-74RylMUc7gBm7b6bHE7i0UkJJc396KOvQtWX1AILS0-cNP1La2yDc3AAMHJj32-j2KiwUw..&type=2&query=%E5%A4%A7%E6%A8%A1%E5%9E%8B&token=B49830EC761ECB00DADCE40A1E5CC55BDBFD40E368CB7341&k=54&h=x",
    }
)

print(result)
