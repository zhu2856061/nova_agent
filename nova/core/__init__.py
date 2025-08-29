import os

from .utils import load_yaml_config, set_log

set_log()

config_path = os.environ.get("CONFIG_PATH", "../config.yaml")

print(f"Loading configuration from {config_path}")

# Load configuration
CONF = load_yaml_config(config_path)
