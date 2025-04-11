import time
from typing import Dict, Optional
from utils.kling_client import KlingAPIClient

class KlingTaskManager:
    """Manages Kling API tasks and their lifecycle."""
    
    def __init__(self, client: KlingAPIClient):
        self.client = client
    
    def create_image_to_video(self, prompt: str, negative_prompt: str = "",
                            duration: int = 5, aspect_ratio: str = "1:1",
                            mode: str = "std", cfg_scale: float = 0.5,
                            image_url: Optional[str] = None,
                            service_mode: str = "public",
                            camera_control: Optional[Dict] = None) -> Dict:
        """
        Create a video generation task and return the task details.
        Uses PAYG mode by default.
        
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
        # Ensure duration is an integer
        try:
            duration = int(duration)
        except (ValueError, TypeError):
            print(f"Converting duration {duration} to integer")
            # Try to convert to float first, then to int
            try:
                duration = int(float(duration))
            except (ValueError, TypeError):
                print(f"Could not convert duration {duration} to number, using default of 5")
                duration = 5
                
        # Ensure duration is either 5 or 10
        if duration not in [5, 10]:
            print(f"Invalid duration {duration}, must be either 5 or 10 seconds. Using default of 5.")
            duration = 5
            
        # Ensure cfg_scale is a float
        try:
            cfg_scale = float(cfg_scale)
        except (ValueError, TypeError):
            print(f"Converting cfg_scale {cfg_scale} to float")
            try:
                cfg_scale = float(str(cfg_scale).replace(',', '.'))
            except (ValueError, TypeError):
                print(f"Could not convert cfg_scale {cfg_scale} to float, using default of 0.5")
                cfg_scale = 0.5
                
        # Ensure cfg_scale is between 0 and 1
        if not 0 <= cfg_scale <= 1:
            print(f"Invalid cfg_scale {cfg_scale}, must be between 0 and 1. Using default of 0.5.")
            cfg_scale = 0.5
            
        return self.client.create_task(
            prompt=prompt,
            negative_prompt=negative_prompt,
            duration=duration,
            aspect_ratio=aspect_ratio,
            mode=mode,
            cfg_scale=cfg_scale,
            image_url=image_url,
            service_mode=service_mode,
            camera_control=camera_control
        )
    
    def wait_for_completion(self, task_id: str, check_interval: int = 10,
                          timeout: int = 600) -> Dict:
        """
        Wait for a task to complete and return the final result.
        
        Args:
            task_id: The ID of the task to monitor
            check_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds
            
        Returns:
            Dict containing the final task result
        """
        if not task_id:
            raise ValueError("Task ID is required")
            
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError("Task monitoring timed out")
            
            status = self.client.get_task_status(task_id)
            
            # Check status in the nested data structure
            task_status = status.get('data', {}).get('status')
            if task_status == "completed":
                return status
            elif task_status == "failed":
                error = status.get('data', {}).get('error', {})
                error_message = error.get('message', 'Unknown error')
                error_detail = error.get('detail', '')
                error_code = error.get('code', 0)
                raw_message = error.get('raw_message', '')
                
                # Create a detailed error message
                detailed_error = f"Task failed with code {error_code}: {error_message}"
                if error_detail:
                    detailed_error += f"\nDetail: {error_detail}"
                if raw_message:
                    detailed_error += f"\nRaw message: {raw_message}"
                
                # Include the full response for debugging
                detailed_error += f"\nFull response: {status}"
                
                raise Exception(detailed_error)
            
            time.sleep(check_interval)
