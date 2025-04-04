import logging
import os
import time
import requests
import glob
import base64
from typing import Dict, Any, List, Optional
from utils.error_handling import retry, circuit_breaker, VideoGenerationError
from utils.security import get_api_key, rate_limit_check
import openai

class VideoGenAgent:
    def __init__(self, api_provider: str = "runway"):
        """
        Initialize the VideoGenAgent.
        
        Args:
            api_provider: The video generation API provider to use
                          Options: "runway", "pika", "suno"
        """
        self.logger = logging.getLogger(__name__)
        self.api_provider = api_provider.lower()
        
        # Set up API key based on provider
        if self.api_provider == "runway":
            self.api_key = get_api_key("RUNWAYML_API_SECRET")
            if not self.api_key:
                raise ValueError("Runway API key not found in environment variables")
        elif self.api_provider == "pika":
            self.api_key = get_api_key("PIKA_API_KEY")
            if not self.api_key:
                raise ValueError("Pika API key not found in environment variables")
        elif self.api_provider == "suno":
            self.api_key = get_api_key("MUSICAPI_KEY")
            if not self.api_key:
                raise ValueError("Suno/MusicAPI key not found in environment variables")
        else:
            raise ValueError(f"Unsupported API provider: {api_provider}")
        
        # Set up OpenAI API key
        openai_api_key = get_api_key("OPENAI_API_KEY")
        if openai_api_key:
            openai.api_key = openai_api_key
            
        # Create data directories if they don't exist
        os.makedirs("data/raw_clips", exist_ok=True)
        os.makedirs("data/images", exist_ok=True)
    
    def select_image_for_scene(self, prompt: str, description: str) -> str:
        """
        Use OpenAI to select the most appropriate image for a scene.
        
        Args:
            prompt: The text prompt for the scene
            description: The scene description
            
        Returns:
            Path to the selected image
        """
        try:
            # Get all images from the images directory
            image_paths = glob.glob("data/images/*.*")
            
            if not image_paths:
                self.logger.warning("No images found in data/images directory")
                # Return default image URL if no local images are available
                return "https://framerusercontent.com/images/0vCKfdMyMxLCjtqWJ2bUQihEwk.png?scale-down-to=512"
            
            # Extract just the filenames for easier matching
            image_names = [os.path.basename(img) for img in image_paths]
            
            # If OpenAI API key is not available, return a random image
            if not openai.api_key:
                self.logger.warning("OpenAI API key not available, selecting random image")
                import random
                return image_paths[random.randint(0, len(image_paths) - 1)]
            
            # Create a prompt for OpenAI
            selection_prompt = f"""
            Select the most appropriate image for this video scene:
            
            Scene prompt: {prompt}
            Scene description: {description}
            
            Available images:
            {', '.join(image_names)}
            
            Return only the filename of the best matching image.
            """
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": selection_prompt}]
            )
            
            # Extract the selected image name
            selected_image_name = response.choices[0].message.content.strip()
            self.logger.info(f"OpenAI selected image: {selected_image_name}")
            
            # Find the full path
            for img_path in image_paths:
                if selected_image_name.lower() in img_path.lower():
                    self.logger.info(f"Using image: {img_path}")
                    return img_path
                    
            # Fallback to the first image if no match
            self.logger.warning(f"No match found for '{selected_image_name}', using first image")
            return image_paths[0]
            
        except Exception as e:
            self.logger.error(f"Error selecting image: {str(e)}")
            # Return the first image as fallback
            if image_paths:
                return image_paths[0]
            else:
                return "https://framerusercontent.com/images/0vCKfdMyMxLCjtqWJ2bUQihEwk.png?scale-down-to=512"
    
    @retry(max_attempts=3, initial_delay=5.0, backoff_factor=2.0)
    @circuit_breaker(failure_threshold=3, reset_timeout=600.0)
    def generate_clip(self, prompt: str, motion_prompt: Optional[str] = None, 
                     duration: float = 4.0, image_path: Optional[str] = None) -> str:
        """
        Generate a video clip based on the prompt.
        
        Args:
            prompt: Text prompt describing the scene
            motion_prompt: Optional motion prompt for dynamic elements
            duration: Desired duration in seconds (may be limited by API)
            image_path: Path to an image to use as the base for video generation
            
        Returns:
            Path to the downloaded video clip
            
        Raises:
            VideoGenerationError: If video generation fails
        """
        try:
            # Check rate limits
            if not rate_limit_check(f"video_gen_{self.api_provider}", max_calls=5, window_seconds=60):
                self.logger.warning(f"Rate limit exceeded for {self.api_provider}")
                time.sleep(10)  # Wait before retrying
                
            # Generate clip based on provider
            if self.api_provider == "runway":
                return self._generate_runway_clip(prompt, motion_prompt, duration, image_path)
            elif self.api_provider == "pika":
                return self._generate_pika_clip(prompt, duration)
            elif self.api_provider == "suno":
                return self._generate_suno_clip(prompt, duration)
                
        except Exception as e:
            self.logger.error(f"Error generating video clip: {str(e)}")
            raise VideoGenerationError(f"Error generating video clip: {str(e)}")
    
    def generate_clips(self, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate video clips for all scenes in the script.
        
        Args:
            script: Script dictionary with metadata and scenes
            
        Returns:
            List of dictionaries with scene info and clip paths
        """
        self.logger.info(f"Generating {len(script.get('scenes', []))} video clips")
        
        results = []
        
        for i, scene in enumerate(script.get("scenes", [])):
            try:
                self.logger.info(f"Generating clip {i+1}/{len(script.get('scenes', []))}")
                
                # Extract scene info
                prompt = scene.get("prompt")
                description = scene.get("description")
                start_time = scene.get("start_time")
                end_time = scene.get("end_time")
                duration = end_time - start_time if end_time and start_time else 4.0
                
                # Select an appropriate image for this scene
                image_path = self.select_image_for_scene(prompt, description)
                
                # Generate the clip
                clip_path = self.generate_clip(
                    prompt=prompt,
                    motion_prompt=description,
                    duration=min(duration, 8.0),  # Cap at 8 seconds for API limitations
                    image_path=image_path
                )
                
                # Add to results
                results.append({
                    "scene_index": i,
                    "start_time": start_time,
                    "end_time": end_time,
                    "prompt": prompt,
                    "description": description,
                    "image_path": image_path,
                    "clip_path": clip_path
                })
                
                self.logger.info(f"Successfully generated clip {i+1}")
                
            except Exception as e:
                self.logger.error(f"Error generating clip {i+1}: {str(e)}")
                # Continue with next scene instead of failing the whole process
                results.append({
                    "scene_index": i,
                    "start_time": start_time if 'start_time' in locals() else None,
                    "end_time": end_time if 'end_time' in locals() else None,
                    "prompt": prompt if 'prompt' in locals() else None,
                    "description": description if 'description' in locals() else None,
                    "image_path": image_path if 'image_path' in locals() else None,
                    "clip_path": None,
                    "error": str(e)
                })
        
        # Check if we have any successful clips
        successful_clips = [r for r in results if r.get("clip_path")]
        if not successful_clips:
            raise VideoGenerationError("Failed to generate any video clips")
            
        return results
    
    def _generate_runway_clip(self, prompt: str, motion_prompt: Optional[str], duration: float, image_path: Optional[str] = None) -> str:
        """
        Generate a video clip using RunwayML API.
        
        Args:
            prompt: Text prompt describing the scene
            motion_prompt: Optional motion prompt for dynamic elements
            duration: Desired duration in seconds (may be limited by API)
            image_path: Path to an image to use as the base for video generation
            
        Returns:
            Path to the downloaded video clip
        """
        try:
            self.logger.info(f"Generating Runway clip with prompt: {prompt[:50]}...")
            
            # Import RunwayML SDK
            # Note: This requires 'pip install runwayml' to be run first
            try:
                from runwayml import RunwayML
            except ImportError:
                self.logger.error("RunwayML SDK not installed. Please run 'pip install runwayml'")
                raise VideoGenerationError("RunwayML SDK not installed")
            
            # Create RunwayML client
            client = RunwayML()
            
            # Use the provided image path or default to a specific image
            default_image_url = "https://framerusercontent.com/images/0vCKfdMyMxLCjtqWJ2bUQihEwk.png?scale-down-to=512"
            
            # Create a task to generate a video using the correct parameter names from the SDK documentation
            self.logger.info("Creating video with RunwayML SDK...")
            
            # Use the correct parameter names from the SDK documentation
            self.logger.info("Using correct parameter names from SDK documentation...")
            
            # Get image data - either from local file or URL
            data_uri = None
            
            if image_path and os.path.isfile(image_path):
                # Load image from local file
                self.logger.info(f"Loading image from local file: {image_path}")
                with open(image_path, "rb") as f:
                    image_data = f.read()
                
                # Determine image type from file extension
                image_type = "jpeg"  # Default to jpeg
                if image_path.lower().endswith(".png"):
                    image_type = "png"
                elif image_path.lower().endswith(".gif"):
                    image_type = "gif"
                elif image_path.lower().endswith(".webp"):
                    image_type = "webp"
                
                # Convert to base64 data URI
                base64_encoded = base64.b64encode(image_data).decode('utf-8')
                data_uri = f"data:image/{image_type};base64,{base64_encoded}"
                self.logger.info(f"Converted local image to data URI (length: {len(data_uri)})")
            else:
                # Download image from URL
                actual_image_url = image_path if image_path and image_path.startswith("http") else default_image_url
                self.logger.info(f"Downloading image from URL: {actual_image_url}")
                
                img_response = requests.get(actual_image_url)
                img_response.raise_for_status()
                
                # Convert image to base64 data URI
                image_data = img_response.content
                base64_encoded = base64.b64encode(image_data).decode('utf-8')
                
                # Determine image type from URL
                image_type = "jpeg"  # Default to jpeg
                if actual_image_url.lower().endswith(".png"):
                    image_type = "png"
                elif actual_image_url.lower().endswith(".gif"):
                    image_type = "gif"
                elif actual_image_url.lower().endswith(".webp"):
                    image_type = "webp"
                    
                # Create data URI
                data_uri = f"data:image/{image_type};base64,{base64_encoded}"
                self.logger.info(f"Converted URL image to data URI (length: {len(data_uri)})")
            
            try:
                # Enhance the prompt with anime style keywords
                anime_style_prompt = f"anime style, 2D cartoon animation, Japanese anime, {motion_prompt or prompt}"
                
                # Create a task to generate a video
                try:
                    # First try with negative prompt (if supported)
                    task_response = client.image_to_video.create(
                        model="gen3a_turbo",
                        prompt_image=data_uri,  # Use base64 data URI
                        prompt_text=anime_style_prompt,
                        negative_prompt="photorealistic, realistic, 3D, live action, real people, human faces, photorealism, realism",
                        ratio="1280:768",
                        watermark=False
                    )
                except Exception as e:
                    # If negative_prompt is not supported, fall back to just using the enhanced prompt
                    if "negative_prompt" in str(e).lower():
                        self.logger.info("Negative prompt not supported, using enhanced prompt only")
                        task_response = client.image_to_video.create(
                            model="gen3a_turbo",
                            prompt_image=data_uri,  # Use base64 data URI
                            prompt_text=anime_style_prompt,
                            ratio="1280:768",
                            watermark=False
                        )
                    else:
                        # Re-raise if it's a different error
                        raise
                
                # Get the task ID
                task_id = task_response.id
                self.logger.info(f"RunwayML task created with ID: {task_id}")
                
                # Poll the task until it's complete
                task_info = None
                status = "PROCESSING"  # Initial status
                
                while status not in ["SUCCEEDED", "FAILED"]:
                    time.sleep(10)  # Wait for ten seconds before polling
                    task_info = client.tasks.retrieve(task_id)
                    
                    # Check if task_info has a status attribute
                    if hasattr(task_info, 'status'):
                        status = task_info.status
                    else:
                        # If no status attribute, check for other indicators
                        if hasattr(task_info, 'error') and task_info.error:
                            status = "FAILED"
                        elif hasattr(task_info, 'output') and task_info.output:
                            status = "SUCCEEDED"
                    
                    self.logger.info(f"Task status: {status}")
                
                if status == "FAILED":
                    error_msg = getattr(task_info, 'error', 'Unknown error')
                    self.logger.error(f"RunwayML task failed: {error_msg}")
                    raise VideoGenerationError(f"RunwayML task failed: {error_msg}")
                
                # Get the video URL from the completed task based on the RunwayML API documentation
                # According to the docs, the output field is an array of URLs
                self.logger.info("Extracting video URL from task response...")
                
                video_url = None
                
                if hasattr(task_info, 'output'):
                    self.logger.info(f"Output found. Type: {type(task_info.output)}")
                    
                    # Handle different possible output formats
                    if isinstance(task_info.output, list) and len(task_info.output) > 0:
                        # If output is a list (array), take the first URL
                        video_url = task_info.output[0]
                        self.logger.info(f"Found URL in output array: {video_url}")
                    elif isinstance(task_info.output, str):
                        # If output is directly a string
                        video_url = task_info.output
                        self.logger.info(f"Output is directly a string URL: {video_url}")
                    elif hasattr(task_info.output, '__getitem__') and len(task_info.output) > 0:
                        # If output is a list-like object
                        try:
                            video_url = task_info.output[0]
                            self.logger.info(f"Found URL in output list-like object: {video_url}")
                        except (IndexError, TypeError):
                            self.logger.warning("Output is list-like but couldn't access first element")
                    else:
                        # Log what we found for debugging
                        self.logger.warning(f"Unexpected output format: {task_info.output}")
                else:
                    self.logger.warning("No output field found in task_info")
                
                # If we still don't have a URL, raise an error
                if not video_url:
                    raise VideoGenerationError("Task completed but no output URL found in the response")
                
                self.logger.info(f"Successfully extracted video URL: {video_url}")
                
                # Download the video
                self.logger.info(f"Downloading video from: {video_url}")
                
                # Create a unique filename
                timestamp = int(time.time())
                filename = f"data/raw_clips/runway_{timestamp}.mp4"
                
                # Download the video
                response = requests.get(video_url, stream=True)
                response.raise_for_status()
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.logger.info(f"Video saved to: {filename}")
                return filename
                
            except Exception as e:
                error_message = str(e)
                
                # Check for credit error and provide a clearer message
                if "You do not have enough credits" in error_message:
                    raise VideoGenerationError(
                        "RunwayML account has insufficient credits. Please add credits to your RunwayML account to generate videos."
                    )
                else:
                    # Re-raise the error for other issues
                    raise
                
        except Exception as e:
            self.logger.error(f"Error generating video with RunwayML: {str(e)}")
            raise VideoGenerationError(f"Error generating video with RunwayML: {str(e)}")
    
    def _generate_pika_clip(self, prompt: str, duration: float) -> str:
        """
        Generate a video clip using Pika API.
        
        This is a placeholder implementation.
        """
        self.logger.info(f"Generating Pika clip with prompt: {prompt[:50]}...")
        
        # Placeholder for API call
        # In a real implementation, you would call the Pika API here
        
        # Simulate API call delay
        time.sleep(2)
        
        # Create a unique filename
        timestamp = int(time.time())
        filename = f"data/raw_clips/pika_{timestamp}.mp4"
        
        # Placeholder for downloading the video
        # In a real implementation, you would download the video from the API response
        
        # For now, just create an empty file as a placeholder
        with open(filename, "w") as f:
            f.write("Placeholder for Pika generated video")
            
        return filename
    
    def _generate_suno_clip(self, prompt: str, duration: float) -> str:
        """
        Generate a video clip using Suno API.
        
        This is a placeholder implementation.
        """
        self.logger.info(f"Generating Suno clip with prompt: {prompt[:50]}...")
        
        # Placeholder for API call
        # In a real implementation, you would call the Suno API here
        
        # Simulate API call delay
        time.sleep(2)
        
        # Create a unique filename
        timestamp = int(time.time())
        filename = f"data/raw_clips/suno_{timestamp}.mp4"
        
        # Placeholder for downloading the video
        # In a real implementation, you would download the video from the API response
        
        # For now, just create an empty file as a placeholder
        with open(filename, "w") as f:
            f.write("Placeholder for Suno generated video")
            
        return filename
