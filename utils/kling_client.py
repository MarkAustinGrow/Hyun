import requests
from typing import Dict, Optional
import logging
import os
from utils.security import get_api_key

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KlingAPIClient:
    """Client for interacting with the Kling API through PiAPI."""
    
    def __init__(self, api_key: Optional[str] = None):
        # Use provided API key or get from environment
        if not api_key:
            api_key = get_api_key("PiAPI_Key")
            
        if not api_key:
            raise ValueError("PiAPI key is required. Please check your .env file.")
            
        self.api_key = api_key
        self.base_url = "https://api.piapi.ai/api/v1"
        # Headers according to PiAPI documentation
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info(f"Initialized PiAPI client with base URL: {self.base_url}")
    
    def create_task(self, prompt: str = "", negative_prompt: str = "",
                   duration: int = 5, aspect_ratio: str = "1:1",
                   mode: str = "std", cfg_scale: float = 0.5,
                   image_url: Optional[str] = None,
                   service_mode: str = "public",
                   camera_control: Optional[Dict] = None) -> Dict:
        """
        Create a new video generation task using PiAPI's unified API schema.
        
        Args:
            prompt: Text prompt to guide the generation (<= 2500 characters)
            negative_prompt: Text prompt for things to avoid (<= 2500 characters)
            duration: Video duration in seconds (5 or 10)
            aspect_ratio: Video aspect ratio (1:1, 16:9, 9:16)
            mode: Generation mode (std or pro)
            cfg_scale: Configuration scale as float (between 0 and 1, recommended: 0.5)
            image_url: Optional URL of the input image for image-to-video
            service_mode: Service mode ("public" for PAYG, "private" for HYA)
            camera_control: Optional camera control parameters for dynamic movement
            
        Returns:
            Dict containing the task response
        """
        endpoint = f"{self.base_url}/task"
        logger.info(f"Creating task with endpoint: {endpoint}")
        
        # Validate inputs
        if len(prompt) > 2500:
            raise ValueError("Prompt must be <= 2500 characters")
        if len(negative_prompt) > 2500:
            raise ValueError("Negative prompt must be <= 2500 characters")
            
        # Ensure duration is an integer
        try:
            duration = int(duration)
        except (ValueError, TypeError):
            logger.warning(f"Converting duration {duration} to integer")
            # Try to convert to float first, then to int
            try:
                duration = int(float(duration))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert duration {duration} to number, using default of 5")
                duration = 5
                
        # Validate duration
        if duration not in [5, 10]:
            logger.warning(f"Invalid duration {duration}, must be either 5 or 10 seconds. Using default of 5.")
            duration = 5
            
        # Validate aspect ratio
        if aspect_ratio not in ["1:1", "16:9", "9:16"]:
            logger.warning(f"Invalid aspect ratio {aspect_ratio}, must be one of: 1:1, 16:9, 9:16. Using default of 1:1.")
            aspect_ratio = "1:1"
            
        # Validate mode
        if mode not in ["std", "pro"]:
            logger.warning(f"Invalid mode {mode}, must be either 'std' or 'pro'. Using default of 'std'.")
            mode = "std"
            
        # Validate service mode
        if service_mode not in ["public", "private", ""]:
            logger.warning(f"Invalid service mode {service_mode}, must be either 'public' or 'private'. Using default of 'public'.")
            service_mode = "public"
            
        # Ensure cfg_scale is a float
        try:
            cfg_scale = float(cfg_scale)
        except (ValueError, TypeError):
            logger.warning(f"Converting cfg_scale {cfg_scale} to float")
            try:
                cfg_scale = float(str(cfg_scale).replace(',', '.'))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert cfg_scale {cfg_scale} to float, using default of 0.5")
                cfg_scale = 0.5
                
        # Validate cfg_scale
        if not 0 <= cfg_scale <= 1:
            logger.warning(f"Invalid cfg_scale {cfg_scale}, must be between 0 and 1. Using default of 0.5.")
            cfg_scale = 0.5
        
        # Base input structure following unified API schema
        input_data = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "cfg_scale": cfg_scale,  # Now sending as float
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "mode": mode
        }
        
        # Add image_url if provided
        if image_url:
            input_data["image_url"] = image_url
            
        # Add camera control if provided, otherwise use default
        if camera_control:
            input_data["camera_control"] = camera_control
        else:
            input_data["camera_control"] = {
                "type": "simple",
                "config": {
                    "horizontal": 0,
                    "vertical": 0,
                    "pan": 0,
                    "tilt": 0,
                    "roll": 0,
                    "zoom": 0
                }
            }
        
        # Following PiAPI's unified API schema
        payload = {
            "model": "kling",
            "task_type": "video_generation",
            "input": input_data,
            "config": {
                "service_mode": service_mode,
                "webhook_config": {
                    "endpoint": "",
                    "secret": ""
                }
            }
        }
        
        try:
            logger.info("Sending request to PiAPI...")
            logger.info(f"Request Headers: {self.headers}")
            logger.info(f"Payload: {payload}")
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"API Error Response: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            logger.error(f"Failed to connect to {endpoint}")
            raise Exception(f"Failed to connect to PiAPI. Please check your internet connection and API endpoint.")
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            raise Exception("Request to PiAPI timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Error communicating with PiAPI: {str(e)}")
    
    def get_task_status(self, task_id: str) -> Dict:
        """
        Get the status of a task using PiAPI's unified API schema.
        
        Args:
            task_id: The ID of the task to check
            
        Returns:
            Dict containing the task status
        """
        endpoint = f"{self.base_url}/task/{task_id}"
        logger.info(f"Checking task status: {endpoint}")
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"API Error Response: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            raise Exception(f"Failed to connect to PiAPI. Please check your internet connection.")
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            raise Exception("Request to PiAPI timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Error communicating with PiAPI: {str(e)}")
