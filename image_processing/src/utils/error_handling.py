# ===== src/utils/error_handling.py =====
import logging
import traceback
from functools import wraps
from typing import Any, Callable, Optional, Type, Union
from ..models.processing_models import ProcessingResult

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Base exception for processing errors."""
    pass


class FileNotFoundError(ProcessingError):
    """File not found error."""
    pass


class InvalidFileError(ProcessingError):
    """Invalid file error."""
    pass


class ProcessingTimeoutError(ProcessingError):
    """Processing timeout error."""
    pass


def handle_processing_errors(
        operation_name: str,
        return_type: Type = ProcessingResult
) -> Callable:
    """
    Decorator to handle processing errors consistently.

    Args:
        operation_name: Name of the operation for logging
        return_type: Type to return on error

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except ProcessingError as e:
                logger.error(f"{operation_name} failed: {e}")
                if return_type == ProcessingResult:
                    return ProcessingResult(
                        file_id=kwargs.get('file_id', 'unknown'),
                        processing_type=operation_name,
                        success=False,
                        processing_time_seconds=0.0,
                        error_message=str(e)
                    )
                raise
            except Exception as e:
                logger.error(f"Unexpected error in {operation_name}: {e}")
                logger.error(traceback.format_exc())
                if return_type == ProcessingResult:
                    return ProcessingResult(
                        file_id=kwargs.get('file_id', 'unknown'),
                        processing_type=operation_name,
                        success=False,
                        processing_time_seconds=0.0,
                        error_message=f"Unexpected error: {str(e)}"
                    )
                raise

        return wrapper

    return decorator
