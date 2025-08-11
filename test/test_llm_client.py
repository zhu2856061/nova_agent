"""

curl -X POST http://0.0.0.0:11021/predict -H 'Content-Type: application/json' -d '{"uid": "123", "businessParam": {"fuid": 139070046, "fage": 21, "fsex": 1, "fcollege_level": 1, "foverdue_max_day": 65, "foverdue_amount": 5028, "fdeduct_strategy_chain_id": 73, "fdeduct_strategy_id": 65}}'

curl -X POST http://mlplatform.fql.com/seldon/mlapp-pre/paytype/predict -H 'Content-Type: application/json' -d '{"uid": "123", "businessParam": {"fuid": 139070046, "fage": 21, "fsex": 1, "fcollege_level": 1, "foverdue_max_day": 65, "foverdue_amount": 5028, "fdeduct_strategy_chain_id": 73, "fdeduct_strategy_id": 65}}'



curl -X GET http://0.0.0.0:12023/health
"""

import requests

inputs = {
    "trace_id": "123",
    "llm_dtype": "BASIC",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "What is the capital of France?",
        },
    ],
}
r = requests.post("http://0.0.0.0:2021/stream_llm", json=inputs)
print(r.json())
