import configparser
import logging
import logging.config
import os
import sys
import re

pattern = re.compile(r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,\s*([^}]+?)\s*)?\}")

def _replace(match: re.Match) -> str:
    name = match.group(1)
    default = match.group(2)
    
    val = os.getenv(name)
    if val is None:
        if default is None:
            raise ValueError(f"Environment variable '{name}' is not set and no default value provided in logging config.")
        return default
        
    return val

def _parse_file(config_path: str) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(config_path)

    for section in cp.sections():
        for opt in cp.options(section):
            raw_val = cp.get(section, opt, raw=True)
            if raw_val is None:
                continue
            new_val = pattern.sub(_replace, raw_val)
            cp.set(section, opt, new_val)

    return cp


def configure_from_logging_ini():
    """
    Configure the root logger using fileConfig() with the file path
    specified by the LOGGING_CONFIG_PATH environment variable.
    
    Returns:
        bool: True if configuration was successful, False otherwise.
    """
    config_path = os.getenv("LOGGING_CONFIG_PATH")

    if not config_path:
        print("INFO: LOGGING_CONFIG_PATH environment variable is not set.")
        return False

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"LOGGING_CONFIG_PATH is set to '{config_path}', but the file was not found.")    

    try:
        config = _parse_file(config_path)

        logging.config.fileConfig(config)

        logger = logging.getLogger(__name__)
        logger.info("Root logger successfully configured based on LOGGING_CONFIG_PATH=%s", config_path)
        return True

    except Exception as e:
        import traceback
        print(f"ERROR: Exception occurred while configuring root logger from '{config_path}' (specified by LOGGING_CONFIG_PATH environment variable). Exception: {traceback.format_exc()}", file=sys.stderr)
        raise e
