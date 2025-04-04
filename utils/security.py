import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

load_dotenv()

def get_api_key(key_name: str) -> Optional[str]:
    """
    Safely retrieve an API key from environment variables.
    
    Args:
        key_name: Name of the environment variable containing the API key
        
    Returns:
        API key if found, None otherwise
    """
    api_key = os.environ.get(key_name)
    
    if not api_key:
        logger.warning(f"API key {key_name} not found in environment variables")
        return None
        
    return api_key

def validate_params(params: Dict[str, Any], required_fields: list) -> bool:
    """
    Validate that required fields are present in the params dictionary.
    
    Args:
        params: Dictionary of parameters to validate
        required_fields: List of field names that must be present
        
    Returns:
        True if all required fields are present, False otherwise
    """
    if not params:
        logger.error("Params dictionary is empty or None")
        return False
        
    missing_fields = [field for field in required_fields if field not in params or params[field] is None]
    
    if missing_fields:
        logger.error(f"Missing required fields: {', '.join(missing_fields)}")
        return False
        
    return True

def sanitize_input(text: str) -> str:
    """
    Sanitize input text to prevent injection attacks.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
        
    # Remove potentially dangerous characters
    sanitized = text.replace("<", "&lt;").replace(">", "&gt;")
    
    return sanitized

def rate_limit_check(resource_name: str, max_calls: int = 10, window_seconds: int = 60) -> bool:
    """
    Simple in-memory rate limiting.
    In a production environment, this would use Redis or another distributed cache.
    
    Args:
        resource_name: Name of the resource being rate limited
        max_calls: Maximum number of calls allowed in the time window
        window_seconds: Time window in seconds
        
    Returns:
        True if the call is allowed, False if rate limited
    """
    # This is a placeholder implementation
    # In a real implementation, you would track calls in a persistent store
    logger.info(f"Rate limit check for {resource_name}: allowed")
    return True
