import sys

sys.path.append("../src")
import os

os.environ["CONFIG_PATH"] = "../config.yaml"

from core.tools import markdown_to_html_tool

data = "# 深圳市2025年8月19日天气综合报告  \n\n## 实时气象数据汇总  \n\n### 气温  \n- **深圳市气象局**（更新时间：15:34）：  \n  气温范围26-31℃，阴天到多云，伴随（雷）阵雨 [1]。  \n- **深圳市气象局**（更新时间：17:45）：  \n  实时温度26.9°C，湿度91%，风速7-8级阵风风险 [3]。  \n- **中国天气网**（更新时间：17:45）：  \n  气温27°C，北风1级，湿度92% [2][4]。  \n\n### 降水概率与天气现象  \n- **深圳市气象局**（15:34更新）：  \n  白天有（雷）阵雨，夜间局地雨势较大 [1]。  \n- **中国天气网**（17:45更新）：  \n  白天阴天，夜间逐步降温并伴随降雨 [2][4]。  \n- **灾害预警**：  \n  深圳市气象局发布8月19-20日强降雨风险提示，需防范城市内涝及地质灾害 [3]。  \n\n### 风速与湿度  \n- **深圳市气象局**（17:45更新）：  \n  风速7-8级阵风风险，湿度91% [3]。  \n- **中国天气网**（17:45更新）：  \n  北风1级，湿度92% [2][4]。  \n\n### 紫外线指数与空气质量  \n- **中国天气网**（17:45更新）：  \n  紫外线指数弱，空气质量优（AQI 19），不适宜洗车、晾晒 [2][4]。  \n\n## 数据来源对比分析  \n1. **温度一致性**：  \n   两机构数据高度一致（26.9-27°C），但深圳市气象局提供更详细的天气现象描述（如阵雨、阵风）。  \n2. **风速差异**：  \n   深圳市气象局监测到7-8级阵风（可能与强对流天气相关），而中国天气网显示风速仅1级，需以气象局数据为准 [3]。  \n3. **更新时效性**：  \n   中国天气网与深圳市气象局均在17:45更新数据，但气象局额外提供灾害预警及长期降雨趋势分析 [1][3]。  \n\n## 长期气象趋势与附加信息  \n- **2025年累计降雨量**：  \n  深圳市气象局数据显示，2025年累计降雨量1,542.3mm（较5年平均值高20%），边境区域达1,762.8mm [3]。  \n- **未来48小时预报**：  \n  8月20日最高温32℃，8月21日多云转晴，8月22日晴天最高温33℃ [2]。  \n- **中长期风险**：  \n  8月23日至31日将持续降雨，40天趋势预测显示高温（33℃）与23次降水事件 [2]。  \n\n## 结论与建议  \n深圳市气象局数据（[1][3]）在风速、灾害预警及长期趋势分析方面更具权威性，建议优先参考。今日需重点关注强降雨及阵风风险，户外活动需做好防雨防暑准备，夜间局地雨势增强可能影响交通。  \n\n### Sources  \n[1] 深圳市气象局（台）: http://www.baidu.com/link?url=cEcP8qT-Qw09_ZQ1ipgFFFeyU9IZkvWPKXpT8mXq2MOksfx3kPvwFgMdFhPjEYYJgQ-eI8f2Y_nQgRHDC2mn4q  \n[2] ...天气预报一周_深圳天气预报7天、15天、40天天查询_中国天气网: http://www.baidu.com/link?url=XI94BuOqWXgblmNhAXduj37_ic9Uf6uqEtY0abrfMMlGeIqSEAYxyr1pS1QHklgSitP4LBdvcjGevRItgdDd1rSSpNau9qkD-caX6dFzhW-Qo0gBTv6slBuIevfy9xxcM5C00U2XGdCuaQ_uNR5G-K  \n[3] 深圳市气象局（台）: http://www.baidu.com/link?url=gpTEfA2utY7fIFyikTMEBWoMVnqXVVtqUC7sMod-GNl8CBtEZk8Yg7BbBuDU7izj  \n[4] 中国天气网-专业天气预报、气象服务门户: http://www.baidu.com/link?url=XI94BuOqWXgblmNhAXdujBRiu2G3uQUxnA3kN9szExZ-r06CRVT_aSzdCdnCX71ZupM5B0KRyUiDqDw9IppCp4SV01QIEWeOG6hHFGZeNay"

# 同步调用
result = markdown_to_html_tool.invoke(
    {
        "md_content": data,
        "output_file": "data.html",
    }
)
