import logging
import time
from functools import wraps
from typing import Callable, Any, TypeVar, Optional

# Type variable for generic function
T = TypeVar('T')

logger = logging.getLogger(__name__)

class VideoProcessingError(Exception):
    """Base exception for video processing errors."""
    pass

class ScriptGenerationError(VideoProcessingError):
    """Exception raised when script generation fails."""
    pass

class VideoGenerationError(VideoProcessingError):
    """Exception raised when video generation fails."""
    pass

class VideoStitchingError(VideoProcessingError):
    """Exception raised when video stitching fails."""
    pass

class UploadError(VideoProcessingError):
    """Exception raised when video upload fails."""
    pass

def retry(max_attempts: int = 3, 
          initial_delay: float = 1.0, 
          backoff_factor: float = 2.0,
          exceptions: tuple = (Exception,)) -> Callable:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            delay = initial_delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"All {max_attempts} retry attempts failed for {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
                    delay *= backoff_factor
            
            # This should never be reached due to the raise in the except block
            raise RuntimeError("Unexpected error in retry logic")
        
        return wrapper
    
    return decorator

def circuit_breaker(failure_threshold: int = 5, 
                   reset_timeout: float = 60.0) -> Callable:
    """
    Circuit breaker decorator to prevent repeated calls to failing services.
    
    Args:
        failure_threshold: Number of failures before opening the circuit
        reset_timeout: Time in seconds before attempting to close the circuit
        
    Returns:
        Decorated function with circuit breaker logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Shared state for the circuit breaker
        state = {
            'failures': 0,
            'open': False,
            'last_failure_time': 0
        }
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            # Check if circuit is open
            if state['open']:
                current_time = time.time()
                if current_time - state['last_failure_time'] > reset_timeout:
                    # Try to close the circuit
                    logger.info(f"Circuit breaker for {func.__name__} attempting to close")
                    state['open'] = False
                    state['failures'] = 0
                else:
                    # Circuit still open
                    logger.warning(f"Circuit breaker for {func.__name__} is open. Call rejected.")
                    raise VideoProcessingError(f"Circuit breaker for {func.__name__} is open")
            
            try:
                result = func(*args, **kwargs)
                # Success, reset failure count
                state['failures'] = 0
                return result
            except Exception as e:
                # Increment failure count
                state['failures'] += 1
                state['last_failure_time'] = time.time()
                
                # Check if we should open the circuit
                if state['failures'] >= failure_threshold:
                    state['open'] = True
                    logger.error(
                        f"Circuit breaker for {func.__name__} opened after {failure_threshold} failures"
                    )
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    return decorator
