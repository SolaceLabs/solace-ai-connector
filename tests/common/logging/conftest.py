import logging
import pytest

@pytest.fixture(autouse=True)
def isolated_logging():
    """
    Fixture to prevent tests from altering main logging configuration.
    Main logging application state is saved before each test and restored after every test.
    """
    # Save original state of root logger
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    original_disabled = root_logger.disabled

    # Save state of all existing loggers
    original_logger_states = {}
    for name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        if hasattr(logger, 'handlers'):
            original_logger_states[name] = {
                'handlers': logger.handlers[:],
                'level': logger.level,
                'disabled': logger.disabled,
                'propagate': logger.propagate
            }

    yield

    # Clear changes done within tests and restore original state
    root_logger.handlers.clear()
    root_logger.handlers.extend(original_handlers)
    root_logger.setLevel(original_level)
    root_logger.disabled = original_disabled

    for name, state in original_logger_states.items():
        logger = logging.getLogger(name)
        if hasattr(logger, 'handlers'):
            logger.handlers.clear()
            logger.handlers.extend(state['handlers'])
            logger.setLevel(state['level'])
            logger.disabled = state['disabled']
            logger.propagate = state['propagate']
