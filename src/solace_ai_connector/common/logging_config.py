import logging
import logging.config
import os
import sys


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
        logging.config.fileConfig(config_path)
        logger = logging.getLogger(__name__)
        logger.info(f"Root logger successfully configured based on LOGGING_CONFIG_PATH={config_path}")
        return True

    except Exception as e:
        import traceback
        print(f"ERROR: Exception occurred while configuring root logger from '{config_path}' (specified by LOGGING_CONFIG_PATH environment variable). Exception: {traceback.format_exc()}", file=sys.stderr)
        raise e
