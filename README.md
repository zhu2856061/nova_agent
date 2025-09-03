## 项目运行

### 项目环境
python 3.12

安装uv库
```shell
pip install nv
```

根目录下执行
```shell
uv sync
```

### 启动服务
进入scripts目录下执行
``` shell
uv run python run_server.py
```

### 启动前端界面
进入web-ui目录下执行
``` shell
uv run streamlit run st_main.py
```


## 项目进度

🚀[2025-08-01] 完成LLM部分
1 异步请求LLM - async_llm.py

🚀[2025-08-11] 完成LLM的所有功能和服务
1 llm 采用 ChatLiteLLMRouter 管理
2 llm 添加缓存功能（缓存改写）
3 加入结构化输出-with_structured_output
4 完成llm的服务化和stream llm 的服务化

🚀[2025-08-11] 加入工具 Crawl4AI 实现爬取数据
1 需要安装 playwright ``` playwright install ``` ``` playwright install-deps ```

🚀[2025-08-20] 完成researcher Agent的创建，并运行成功

🚀[2025-08-27] 完成deepresearcher Task的创建，并运行成功


[todo]
- 构建前端界面展示
- 具备llm chat 功能
- 具备llm agent 功能
- 具备llm task 功能





