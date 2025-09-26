export PYTHONPATH=..
export CONFIG_PATH="../config.yaml"
uv run uvicorn nova.main:app --host 0.0.0.0 --port 2021