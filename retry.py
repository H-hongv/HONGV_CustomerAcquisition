"""API retry utility with exponential backoff."""
import time
import random
from functools import wraps
from typing import Type, Tuple, Callable
from logger import logger

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 2.0  # seconds base


def retry_on_error(
    max_retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    component: str = "",
):
    """Decorator: retry function with exponential backoff on failure."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = backoff_base * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"[Retry] {component}.{func.__name__} attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {delay:.1f}s"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[Retry] {component}.{func.__name__} all {max_retries} attempts failed: {e}"
                        )
            raise last_error
        return wrapper
    return decorator


def safe_api_call(func: Callable, *args, component: str = "", **kwargs):
    """Call function with retry and error translation."""
    from error_handler import friendly_error
    decorated = retry_on_error(max_retries=3, component=component)(func)
    try:
        return decorated(*args, **kwargs), None
    except Exception as e:
        return None, friendly_error(e, component)
