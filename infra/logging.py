import logging
import logging.config
import sys
import os
from typing import Dict, Any
from datetime import datetime
import json
import structlog
from pathlib import Path

# Logger names as mentioned in README
EVENT_LOGGER_NAME = "sentinel.events"
TRACE_LOGGER_NAME = "sentinel.traces"

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if they exist
        if hasattr(record, 'conversation_id'):
            log_obj['conversation_id'] = record.conversation_id
        if hasattr(record, 'agent_name'):
            log_obj['agent_name'] = record.agent_name
        if hasattr(record, 'tool_name'):
            log_obj['tool_name'] = record.tool_name
        if hasattr(record, 'processing_time'):
            log_obj['processing_time'] = record.processing_time
        if hasattr(record, 'user_id'):
            log_obj['user_id'] = record.user_id
            
        return json.dumps(log_obj)

def setup_logging(log_level: str = "INFO", 
                 log_dir: str = "./logs",
                 enable_console: bool = True,
                 enable_file: bool = True) -> None:
    """
    Sets up comprehensive logging configuration for SentinelMCP
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        enable_console: Whether to log to console
        enable_file: Whether to log to files
    """
    
    # Create logs directory if it doesn't exist
    if enable_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Define log levels
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    handlers = {}
    
    # Console handler
    if enable_console:
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        }
    
    # File handlers
    if enable_file:
        # General application logs
        handlers['file_general'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'structured',
            'filename': f'{log_dir}/sentinel_general.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
        
        # Event logs (structured for analysis)
        handlers['file_events'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'structured',
            'filename': f'{log_dir}/sentinel_events.log',
            'maxBytes': 10485760,
            'backupCount': 10
        }
        
        # Trace logs (detailed execution traces)
        handlers['file_traces'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'structured',
            'filename': f'{log_dir}/sentinel_traces.log',
            'maxBytes': 10485760,
            'backupCount': 10
        }
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
            'structured': {
                '()': StructuredFormatter,
            }
        },
        'handlers': handlers,
        'loggers': {
            '': {  # Root logger
                'handlers': ['console'] if enable_console else [],
                'level': log_level,
                'propagate': False
            },
            'sentinel': {
                'handlers': (['console'] if enable_console else []) + 
                          (['file_general'] if enable_file else []),
                'level': log_level,
                'propagate': False
            },
            EVENT_LOGGER_NAME: {
                'handlers': (['file_events'] if enable_file else []) + 
                          (['console'] if enable_console else []),
                'level': 'INFO',
                'propagate': False
            },
            TRACE_LOGGER_NAME: {
                'handlers': (['file_traces'] if enable_file else []) + 
                          (['console'] if enable_console else []),
                'level': 'DEBUG',
                'propagate': False
            },
            'uvicorn': {
                'handlers': (['console'] if enable_console else []) + 
                          (['file_general'] if enable_file else []),
                'level': 'INFO',
                'propagate': False
            },
            'fastapi': {
                'handlers': (['console'] if enable_console else []) + 
                          (['file_general'] if enable_file else []),
                'level': 'INFO',
                'propagate': False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(config)

class EventLogger:
    """Specialized logger for business events"""
    
    def __init__(self):
        self.logger = logging.getLogger(EVENT_LOGGER_NAME)
    
    def log_request_start(self, conversation_id: str, question: str, user_id: str = None):
        """Log the start of a request processing"""
        self.logger.info(
            "Request processing started",
            extra={
                'conversation_id': conversation_id,
                'question': question[:100] + "..." if len(question) > 100 else question,
                'user_id': user_id,
                'event_type': 'request_start'
            }
        )
    
    def log_request_complete(self, conversation_id: str, processing_time: float, 
                           success: bool, error: str = None):
        """Log the completion of a request"""
        self.logger.info(
            f"Request processing {'completed' if success else 'failed'}",
            extra={
                'conversation_id': conversation_id,
                'processing_time': processing_time,
                'success': success,
                'error': error,
                'event_type': 'request_complete'
            }
        )
    
    def log_agent_execution(self, conversation_id: str, agent_name: str, 
                          execution_time: float, success: bool, error: str = None):
        """Log agent execution"""
        self.logger.info(
            f"Agent {agent_name} {'completed' if success else 'failed'}",
            extra={
                'conversation_id': conversation_id,
                'agent_name': agent_name,
                'execution_time': execution_time,
                'success': success,
                'error': error,
                'event_type': 'agent_execution'
            }
        )
    
    def log_tool_call(self, conversation_id: str, tool_name: str, 
                     execution_time: float, success: bool, error: str = None):
        """Log tool call execution"""
        self.logger.info(
            f"Tool {tool_name} {'executed successfully' if success else 'failed'}",
            extra={
                'conversation_id': conversation_id,
                'tool_name': tool_name,
                'execution_time': execution_time,
                'success': success,
                'error': error,
                'event_type': 'tool_call'
            }
        )
    
    def log_document_ingestion(self, file_path: str, chunks_created: int, 
                              processing_time: float, success: bool, error: str = None):
        """Log document ingestion"""
        self.logger.info(
            f"Document ingestion {'completed' if success else 'failed'}: {file_path}",
            extra={
                'file_path': file_path,
                'chunks_created': chunks_created,
                'processing_time': processing_time,
                'success': success,
                'error': error,
                'event_type': 'document_ingestion'
            }
        )

class TraceLogger:
    """Specialized logger for detailed execution traces"""
    
    def __init__(self):
        self.logger = logging.getLogger(TRACE_LOGGER_NAME)
    
    def trace_workflow_step(self, conversation_id: str, step: int, agent_name: str, 
                           action: str, context_data: Dict[str, Any] = None):
        """Trace workflow execution steps"""
        self.logger.debug(
            f"Workflow step {step}: {agent_name} - {action}",
            extra={
                'conversation_id': conversation_id,
                'step': step,
                'agent_name': agent_name,
                'action': action,
                'context_data': context_data,
                'event_type': 'workflow_step'
            }
        )
    
    def trace_retrieval(self, conversation_id: str, query: str, 
                       documents_found: int, query_time: float):
        """Trace retrieval operations"""
        self.logger.debug(
            f"Document retrieval: {documents_found} documents found for query",
            extra={
                'conversation_id': conversation_id,
                'query': query[:100] + "..." if len(query) > 100 else query,
                'documents_found': documents_found,
                'query_time': query_time,
                'event_type': 'retrieval'
            }
        )
    
    def trace_policy_check(self, conversation_id: str, policy_result: Dict[str, Any]):
        """Trace policy checking"""
        self.logger.debug(
            "Policy check completed",
            extra={
                'conversation_id': conversation_id,
                'policy_approved': policy_result.get('approved', False),
                'violations': policy_result.get('violations', []),
                'requires_review': policy_result.get('requires_review', False),
                'event_type': 'policy_check'
            }
        )

# Global logger instances
event_logger = EventLogger()
trace_logger = TraceLogger()

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(f"sentinel.{name}")

def get_event_logger() -> EventLogger:
    """Get the global event logger instance"""
    return event_logger

def get_trace_logger() -> TraceLogger:
    """Get the global trace logger instance"""
    return trace_logger

# Legacy function for backwards compatibility
def enable_logs(level=logging.INFO):
    """Legacy function - use setup_logging instead"""
    setup_logging(log_level=logging.getLevelName(level))
