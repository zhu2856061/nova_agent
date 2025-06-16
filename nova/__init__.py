import os

from .utils import load_yaml_config, set_dotenv, set_log

set_log()

config_path = os.getenv("CONFIG_PATH", "config.yaml")


# Load configuration
CONF = load_yaml_config(config_path)

#
set_dotenv(CONF["SYSTEM"]["ENV_PATH"])
