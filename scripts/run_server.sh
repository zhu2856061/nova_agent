export PYTHONPATH=..
export CONFIG_PATH="../config.yaml"

export TASK_DIR="../merlin"
export ENV_PATH="../.env"

export PROMPT_PATH="../prompts"
export SKILL_PATH="../skills"
export CONTAINER_PATH="../containers"

uv run uvicorn backend.main:app --host 0.0.0.0 --port 2021