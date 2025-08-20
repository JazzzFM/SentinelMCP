import logging
from saptiva_agents.core import EVENT_LOGGER_NAME, TRACE_LOGGER_NAME

def enable_logs(level=logging.INFO):
    logging.basicConfig(level=level)
    logging.getLogger(EVENT_LOGGER_NAME).setLevel(logging.INFO)
    logging.getLogger(TRACE_LOGGER_NAME).setLevel(logging.DEBUG)
