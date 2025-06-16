# nova agent

# 测试llm

```python
from nova.llms import get_llm_by_type, with_structured_output
from pydantic import BaseModel

llm = get_llm_by_type("BASIC")


# 定义输出结构
class Person(BaseModel):
    name: str
    age: int
    hobbies: list[str]


llm = with_structured_output(llm, Person)

result = llm.invoke("生成一个用户数据")
# res = llm.invoke("你是谁")
print(result)
```

# 测试workflow
```python
from nova.graph import app

state = app.invoke(
    {
        "messages": [{"role": "user", "content": "现在深圳的气温是怎么样的"}],
    },
    config={
        "task_id": "merlin",
        "coordinator_model": "MYBASIC",
        "planner_model": "MYBASIC",
        "supervisor_model": "MYBASIC",
        "reporter_model": "MYBASIC",
        "is_serp_before_planning": False,
    },  # type: ignore
)
print(state["messages"])
```



## 项目启动

【注】基于了解uv工具的基础上进行

1 pyproject.toml 和 uv.lock 务必主要是否存在

1.1 将.env.example 换成.env，并写上自己的环境变量 API_KEY
1.2 将 config.yaml 中的 LLM里面的模型换成自己的模型

2 拿到项目后，进入项目目录le_agent, 执行环境同步(若没有uv命令，则安装pip install uv)
```shell
uv sync 
```
3 环境同步好后，会在le_agent 生成虚拟环境目录.venv， 到此一切正常的话，即可打包项目
```shell
uv run pip install  -e .
```

4 项目打包完成后，即可启动服务
``` shell
uv run langgraph dev
```

5 服务启动后，会提供后端接口
- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs
