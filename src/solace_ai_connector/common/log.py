# log.py - Logging utilities

import sys
import logging
import logging.handlers


log = logging.getLogger("solace_ai_connector")


# Function to setup the configuration for the logger
def setup_log(logFilePath, stdOutLogLevel, fileLogLevel):
    # Set the global logger level to the lowest of the two levels
    log.setLevel(min(stdOutLogLevel, fileLogLevel))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdOutLogLevel)
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler.setFormatter(stream_formatter)

    # Create an empty file at logFilePath (this will overwrite any existing content)
    with open(logFilePath, "w") as file:
        file.write("")        

    # file_handler = logging.handlers.TimedRotatingFileHandler(
    #    filename=logFilePath, when='midnight', backupCount=30, mode='w')
    file_handler = logging.FileHandler(filename=logFilePath, mode="a")
    file_formatter = logging.Formatter("%(asctime)s |  %(levelname)s: %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(fileLogLevel)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)
