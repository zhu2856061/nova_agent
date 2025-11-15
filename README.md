## 项目运行

### 项目环境
python 3.12

安装uv库
```shell
pip install uv
```

根目录下执行
```shell
uv sync
```

注意： ⚠️ 使用里面的researcher, 需要安装 playwright ``` playwright install ``` ``` playwright install-deps ```

### 启动服务
进入scripts目录下执行
``` shell
sh run_server.sh
```

### 启动前端界面
进入scripts目录下执行
``` shell
sh run_web.sh
```

### [可选项] 可以采用langgraph 自带的langgraph-cli启动一个本地 LangGraph Studio 实例
进入scripts目录下执行
```shell
sh run_langgraph_cli.sh
```



## 项目进度

🚀[2025-08-01] 完成LLM部分
1 异步请求LLM - async_llm.py

🚀[2025-08-11] 完成LLM的所有功能和服务
1 llm 采用 ChatLiteLLMRouter 管理
2 llm 添加缓存功能（缓存改写）
3 加入结构化输出-with_structured_output
4 完成llm的服务化和stream llm 的服务化

🚀[2025-08-11] 加入工具 Crawl4AI 实现爬取数据（需要安装 playwright）

🚀[2025-08-20] 完成researcher Agent的创建，并运行成功

🚀[2025-08-27] 完成deepresearcher Task的创建，并运行成功

🚀[2025-09-03] 完成 llm chat agent team的前端界面构建，并流程走通

🚀[2025-09-08] 完成 memory 模块，并构建了memorize agent 验证成功

🚀[2025-09-09] 解决流式输出bug

🚀[2025-09-09] 加入langgraph dev 模式，方便进行studio的测试Agent,同时将memory相关的全部改成异步处理

🚀[2025-09-16] 加入微信公众号检索和爬取工具，用于获得高质量技术文章

🚀[2025-09-26] 前端切换，不再使用streamlit，采用reflex

🚀[2025-10-16] 完成小说生成 ainovel

🚀[2025-11-14] 完成小说ainovel 的互动操作模式

[todo]
- 小说生成，需要新增各种人工编辑器（以章节为单位进行）
- 新增代码分析/解决/生成 agent
- 知乎检索