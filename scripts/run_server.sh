export PYTHONPATH=..
export CONFIG_PATH="../config.yaml"
export ENV_PATH="../.env"

export CONTAINER_PATH="../containers"

uv run uvicorn backend.main:app --host 0.0.0.0 --port 2021