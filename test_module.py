from nova.graph import app

state = app.invoke(
    {
        "messages": [{"role": "user", "content": "现在深圳的天气是怎么样的"}],
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
