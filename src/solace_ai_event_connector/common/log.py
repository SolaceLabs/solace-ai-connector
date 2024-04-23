# log.py - Logging utilities

import sys
import logging
import logging.handlers


log = logging.getLogger("mylog")
log.setLevel(logging.DEBUG)

# Function to setup the configuration for the logger
def setup_log(logFilePath, stdOutLogLevel, fileLogLevel):
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdOutLogLevel)
    stream_formatter = logging.Formatter(
        '%(message)s')
    stream_handler.setFormatter(stream_formatter)

    #file_handler = logging.handlers.TimedRotatingFileHandler(
    #    filename=logFilePath, when='midnight', backupCount=30, mode='w')
    file_handler = logging.FileHandler(
        filename=logFilePath, mode='w')
    file_formatter = logging.Formatter(
        '%(asctime)s |  %(levelname)s: %(message)s')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(fileLogLevel)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)

