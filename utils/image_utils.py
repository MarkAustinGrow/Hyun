import logging
import requests
from io import BytesIO
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)

def check_image_dimensions(image_url, min_width=300, min_height=300):
    """
    Check if the image meets the minimum dimension requirements.
    
    Args:
        image_url: URL of the image to check
        min_width: Minimum required width in pixels (default: 300)
        min_height: Minimum required height in pixels (default: 300)
        
    Returns:
        tuple: (is_valid, width, height) where is_valid is a boolean indicating if the image meets requirements
    """
    try:
        logger.info(f"Checking image dimensions for: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        
        logger.info(f"Image dimensions: {width}x{height} pixels")
        
        if width < min_width or height < min_height:
            logger.error(f"Image dimensions ({width}x{height}) are below the minimum requirement of {min_width}x{min_height}px")
            return False, width, height
        
        return True, width, height
    except Exception as e:
        logger.error(f"Error checking image dimensions: {str(e)}")
        return False, 0, 0

def resize_image(image_url, min_width=300, min_height=300):
    """
    Resize an image to meet minimum dimension requirements while maintaining aspect ratio.
    
    Args:
        image_url: URL of the image to resize
        min_width: Minimum required width in pixels (default: 300)
        min_height: Minimum required height in pixels (default: 300)
        
    Returns:
        BytesIO: Image data as BytesIO object, or None if resize failed
    """
    try:
        logger.info(f"Attempting to resize image: {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        
        # Calculate new dimensions while maintaining aspect ratio
        if width < min_width or height < min_height:
            # Calculate scaling factors
            width_scale = min_width / width if width < min_width else 1
            height_scale = min_height / height if height < min_height else 1
            
            # Use the larger scaling factor to ensure both dimensions meet minimums
            scale = max(width_scale, height_scale)
            
            # Calculate new dimensions
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
            
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Save to BytesIO
            output = BytesIO()
            img_format = img.format if img.format else 'JPEG'
            resized_img.save(output, format=img_format)
            output.seek(0)
            
            return output
        else:
            logger.info(f"Image already meets minimum dimensions: {width}x{height}")
            # Image already meets requirements, return original
            output = BytesIO()
            img_format = img.format if img.format else 'JPEG'
            img.save(output, format=img_format)
            output.seek(0)
            return output
            
    except Exception as e:
        logger.error(f"Error resizing image: {str(e)}")
        return None
