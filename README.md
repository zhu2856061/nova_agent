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

🚀[2026-02-06] 将代码拆分成3部分：frontend 前端，backend 后端，nova 核心件

🚀[2026-02-12] 基于新的架构，开发-对话系统中话术质量评估Agent

🚀[2026-02-13] skill能力 - 复杂任务的todo list 能力 [重构 TodoListMiddleware]

🚀[todo] 文件操作能力：ls, read_file, write_file, edit_file, glob, and grep [重构 FilesystemMiddleware]

⏳[todo] 设计一个通用型agent,其核心结构为：
    预置工具：
        1 网络搜索
        2 代码执行（依赖sandbox）
        3 文件操作
        4 询问澄清
        5 子任务Agent创建

    预置环境：sandbox



⏳[todo] skill能力
分析deepagents 的源码，其中的中间件的能力是 before_agent, before_model, after_model, after_agent, wrap_model_call, wrap_tool_call
其中间件的所有能力都可以转换成graph中的节点，其中 before_agent, before_model, after_model, after_agent 本质就是这样设计的
而 wrap_model_call, wrap_tool_call 两个主要就是在model请求的时候和tool执行的时候在外层包装功能

[todo]
- skill能力，这里主要是去复用deepagent，将skill能力加入其中
- 新增代码分析/解决/生成 agent
- 知乎检索