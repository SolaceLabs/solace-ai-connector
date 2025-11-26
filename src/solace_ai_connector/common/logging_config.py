import configparser
import logging
import logging.config
import os
import sys
import re
import json
import yaml

from solace_ai_connector.common.exceptions import InitializationError

logging_initialized = False

# Regex pattern for environment variable substitution: ${VAR_NAME} or ${VAR_NAME, default_value}
pattern = re.compile(r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,\s*([^}]+?)\s*)?\}")

def _replace(match: re.Match) -> str:
    """Replace environment variable references with their values.
    
    Args:
        match: Regex match object containing variable name and optional default value eg ${VAR_NAME, default_value}
        
    Returns:
        str: The environment variable value or default value
        
    Raises:
        ValueError: If environment variable is not set and no default is provided
    """
    name = match.group(1)
    default = match.group(2)
    
    val = os.getenv(name)
    if val is None:
        if default is None:
            raise ValueError(f"Environment variable '{name}' is not set and no default value provided in logging config.")
        return default
        
    return val

def _is_ini_format(content: str) -> bool:
    """Check if the content is in INI format by looking for section headers.

    Args:
        content: String content of the configuration file
    """
    # Look for INI section headers e.g. [formatters]
    if re.search(r'^\s*\[.+\]\s*$', content, re.MULTILINE):
        return True
    return False

def _parse_file(config_path: str) -> configparser.ConfigParser:
    """Parse an INI configuration file with environment variable substitution.
    
    Args:
        config_path: Path to the INI configuration file
        
    Returns:
        configparser.ConfigParser: Parsed configuration with env vars substituted
    """
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


def configure_from_file():
    global logging_initialized
    if logging_initialized:
        return True

    config_path = os.getenv("LOGGING_CONFIG_PATH")

    if not config_path:
        return False

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"LOGGING_CONFIG_PATH is set to '{config_path}', but the file was not found.")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if _is_ini_format(content):
            # Use fileConfig for INI files
            config = _parse_file(config_path)
            # disable_existing_loggers can't be set via INI config file. Set it here explicitly.
            logging.config.fileConfig(config, disable_existing_loggers=False)
        else:
            # Substitute environment variables in the given content string.
            config = pattern.sub(_replace, content)
            try:
                dict_config = json.loads(config)
            except ValueError as json_error:
                try :
                    dict_config = yaml.safe_load(config)
                except Exception:
                    raise InitializationError(f"Logging configuration file 'LOGGING_CONFIG_PATH={config_path}' could not be parsed. The configuration must be valid JSON or YAML.")

            logging.config.dictConfig(dict_config)

        logger = logging.getLogger(__name__)
        logger.info("Root logger successfully configured based on LOGGING_CONFIG_PATH=%s", config_path)

        logging_initialized = True
        return True

    except InitializationError:
        raise
    except Exception as e:
        raise InitializationError(
            f"Exception occurred while configuring logging from 'LOGGING_CONFIG_PATH={config_path}'. "
            f"Validate the logging configuration."
        ) from e
