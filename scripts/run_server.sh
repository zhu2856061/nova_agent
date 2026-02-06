export PYTHONPATH=..
export CONFIG_PATH="../config.yaml"
export PROMPT_PATH="../prompts"
export TASK_DIR="../merlin"
export ENV_PATH="../.env"

uv run uvicorn backend.main:app --host 0.0.0.0 --port 2021