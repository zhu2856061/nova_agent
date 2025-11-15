export PYTHONPATH=..
export CONFIG_PATH="../config.yaml"
export PROMPT_PATH="../prompt"
uv run uvicorn nova.main:app --host 0.0.0.0 --port 2021