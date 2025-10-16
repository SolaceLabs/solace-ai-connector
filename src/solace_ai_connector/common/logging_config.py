import logging
import logging.config
import os
import sys
import re
import configparser


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

    # Pattern matches ${ENV_VAR_NAME, default} or ${ENV_VAR_NAME}
    pattern = re.compile(r"\$\{([^,}]+)(?:,([^}]*))?\}")

    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        default = match.group(2)
        # Prefer environment variable if set (even if empty string); fall back to default
        val = os.getenv(name)
        if val is None:
            if default is None:
                raise ValueError(f"Environment variable '{name}' is not set and no default value provided in logging config.")
            val = default
        return val

    try:
        # Load the INI into a ConfigParser (disable interpolation so % in format strings is preserved)
        cp = configparser.ConfigParser(interpolation=None)
        with open(config_path, "r", encoding="utf-8") as f:
            cp.read_file(f)

        # Substitute values in DEFAULT section first
        if cp.defaults():
            for opt, raw_val in list(cp.defaults().items()):
                if raw_val is None:
                    continue
                new_val = pattern.sub(_replace, raw_val)
                cp["DEFAULT"][opt] = new_val

        # Substitute values in each section
        for section in cp.sections():
            for opt in cp.options(section):
                # Use raw get to avoid any interpolation
                raw_val = cp.get(section, opt, raw=True)
                if raw_val is None:
                    continue
                new_val = pattern.sub(_replace, raw_val)
                cp.set(section, opt, new_val)

        # Pass the modified ConfigParser directly to fileConfig
        logging.config.fileConfig(cp)

        logger = logging.getLogger(__name__)
        logger.info("Root logger successfully configured based on LOGGING_CONFIG_PATH=%s", config_path)
        return True

    except Exception as e:
        import traceback
        print(f"ERROR: Exception occurred while configuring root logger from '{config_path}' (specified by LOGGING_CONFIG_PATH environment variable). Exception: {traceback.format_exc()}", file=sys.stderr)
        raise e
