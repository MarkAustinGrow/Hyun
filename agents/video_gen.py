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
                          Options: "runway", "pika", "suno", "kling"
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
        elif self.api_provider == "kling":
            self.kling_api_key = get_api_key("PiAPI_Key")
            if not self.kling_api_key:
                raise ValueError("PiAPI Key for Kling AI not found in environment variables")
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
            elif self.api_provider == "kling":
                return self._generate_kling_clip(prompt, motion_prompt, duration, image_path)
                
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
        
        # Track used clips to enforce diversity
        used_clips = {}
        
        for i, scene in enumerate(script.get("scenes", [])):
            try:
                self.logger.info(f"Generating clip {i+1}/{len(script.get('scenes', []))}")
                
                # Extract scene info
                prompt = scene.get("prompt")
                description = scene.get("description")
                start_time = scene.get("start_time")
                end_time = scene.get("end_time")
                duration = end_time - start_time if end_time and start_time else 4.0
                
                # Initialize image_path variable
                image_path = None
                
                # For Kling AI, always generate new clips instead of reusing existing ones
                if self.api_provider == "kling":
                    self.logger.info("Using Kling AI - generating new clip instead of reusing existing clips")
                    matching_clip = None
                else:
                    # For other providers, check if we have a matching clip in the database
                    # Pass the used_clips dictionary to avoid excessive reuse
                    matching_clip = self._find_matching_clip(description, used_clips)
                
                if matching_clip:
                    # Use existing clip
                    self.logger.info(f"Reusing existing clip: {matching_clip['filename']}")
                    clip_path = matching_clip['filepath']
                    
                    # Update usage statistics
                    self._update_clip_usage(matching_clip['id'])
                    
                    # Track this clip usage for diversity
                    clip_id = matching_clip['id']
                    used_clips[clip_id] = used_clips.get(clip_id, 0) + 1
                    
                    # Select an image for the results (even though we're not using it for generation)
                    # This ensures image_path is always defined
                    image_path = self.select_image_for_scene(prompt, description)
                else:
                    # No matching clip found or using Kling AI, generate a new one
                    self.logger.info("Generating new clip")
                    
                    # Select an appropriate image for this scene
                    image_path = self.select_image_for_scene(prompt, description)
                    
                    # Create a custom class to hold the description and scene data
                    class EnhancedDescription(str):
                        pass
                    
                    # Create an enhanced description with scene data
                    enhanced_description = EnhancedDescription(description)
                    enhanced_description._scene_data = scene
                    
                    # Generate the clip
                    clip_path = self.generate_clip(
                        prompt=prompt,
                        motion_prompt=enhanced_description,
                        duration=min(duration, 8.0),  # Cap at 8 seconds for API limitations
                        image_path=image_path
                    )
                    
                    # Index the new clip
                    clip_id = self._index_new_clip(clip_path, prompt, description)
                    if clip_id:
                        used_clips[clip_id] = 1
                
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
            
            # Create RunwayML client with API key
            client = RunwayML(api_key=self.api_key)
            
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
                # Extract additional parameters from the scene if available
                scene_data = getattr(motion_prompt, '_scene_data', None)
                
                # Default parameters
                seed = None
                video_duration = 5  # Default to 5 seconds
                aspect_ratio = "1280:768"  # Default to landscape
                
                # Extract parameters from scene data if available
                if scene_data:
                    if 'seed' in scene_data:
                        seed = scene_data.get('seed')
                    if 'duration' in scene_data:
                        video_duration = scene_data.get('duration')
                    if 'ratio' in scene_data:
                        aspect_ratio = scene_data.get('ratio')
                
                # Enhance the prompt with anime style keywords and any specific details
                anime_style_prompt = f"anime style, 2D cartoon animation, Japanese anime, {motion_prompt or prompt}"
                
                # Add camera motion if available
                if scene_data and 'camera_motion' in scene_data:
                    anime_style_prompt += f", camera {scene_data.get('camera_motion')}"
                
                # Create a task to generate a video
                try:
                    # Build parameters dictionary
                    video_params = {
                        "model": "gen3a_turbo",
                        "prompt_image": data_uri,  # Use base64 data URI
                        "prompt_text": anime_style_prompt,
                        "negative_prompt": "photorealistic, realistic, 3D, live action, real people, human faces, photorealism, realism",
                        "ratio": aspect_ratio,
                        "duration": video_duration,
                        "watermark": False
                    }
                    
                    # Add seed if available
                    if seed is not None:
                        video_params["seed"] = seed
                    
                    self.logger.info(f"Creating video with parameters: {video_params}")
                    
                    # Create the task
                    task_response = client.image_to_video.create(**video_params)
                except Exception as e:
                    # If negative_prompt is not supported, fall back to just using the enhanced prompt
                    if "negative_prompt" in str(e).lower():
                        self.logger.info("Negative prompt not supported, using enhanced prompt only")
                        # Remove negative_prompt from parameters
                        video_params.pop("negative_prompt", None)
                        task_response = client.image_to_video.create(**video_params)
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
    
    def _parse_scene_description(self, description: str) -> Dict[str, Any]:
        """
        Parse a scene description into semantic components.
        
        Args:
            description: Description of the scene
            
        Returns:
            Dictionary with semantic components
        """
        description_lower = description.lower()
        
        # Initialize components
        components = {
            "character": "",
            "actions": [],
            "settings": [],
            "details": []
        }
        
        # Extract character
        if "yona" in description_lower:
            components["character"] = "yona"
        
        # Common actions in the dataset
        actions = ["guitar", "singing", "dancing", "skates", "playing", "pointing", 
                  "performing", "walking", "jumping"]
        
        # Common settings in the dataset
        settings = ["neon", "city", "beach", "stage", "crowd", "friends", 
                   "night", "sunset", "studio", "street"]
        
        # Extract actions and settings
        words = description_lower.split()
        for word in words:
            # Clean the word
            clean_word = word.strip(",.!?;:\"'()[]{}").lower()
            
            if clean_word in actions and clean_word not in components["actions"]:
                components["actions"].append(clean_word)
            elif clean_word in settings and clean_word not in components["settings"]:
                components["settings"].append(clean_word)
        
        # Extract additional details
        # Look for specific phrases or combinations
        if "neon lights" in description_lower or "neon city" in description_lower:
            if "neon" not in components["settings"]:
                components["settings"].append("neon")
            if "city" not in components["settings"]:
                components["settings"].append("city")
                
        if "playing guitar" in description_lower:
            if "playing" not in components["actions"]:
                components["actions"].append("playing")
            if "guitar" not in components["actions"]:
                components["actions"].append("guitar")
        
        return components
    
    def _calculate_component_match_score(self, scene_components: Dict[str, Any], 
                                        clip_metadata: Dict[str, Any]) -> float:
        """
        Calculate a match score between scene components and clip metadata.
        
        Args:
            scene_components: Components extracted from scene description
            clip_metadata: Metadata from clip record
            
        Returns:
            Match score between 0.0 and 1.0
        """
        score = 0.0
        total_weight = 0.0
        
        # Get filename metadata if available
        filename_metadata = clip_metadata.get("filename_metadata", {})
        if not filename_metadata and isinstance(clip_metadata.get("filename"), str):
            # Parse from filename if metadata not available
            filename = os.path.splitext(clip_metadata["filename"])[0]
            components = self._parse_filename_components(filename)
            filename_metadata = {
                "character": components.get("character", ""),
                "action": components.get("action", ""),
                "setting": components.get("setting", ""),
                "details": components.get("details", [])
            }
        
        # Character match (high weight)
        if scene_components["character"] and filename_metadata.get("character"):
            if scene_components["character"] == filename_metadata["character"]:
                score += 0.3
            total_weight += 0.3
        
        # Action match (highest weight)
        if scene_components["actions"] and filename_metadata.get("action"):
            if filename_metadata["action"] in scene_components["actions"]:
                score += 0.4
            total_weight += 0.4
        
        # Setting match (medium weight)
        if scene_components["settings"] and filename_metadata.get("setting"):
            if filename_metadata["setting"] in scene_components["settings"]:
                score += 0.2
            total_weight += 0.2
        
        # Details match (low weight)
        if scene_components["settings"] and filename_metadata.get("details"):
            details = filename_metadata["details"] if isinstance(filename_metadata["details"], list) else []
            for detail in details:
                if detail in scene_components["settings"]:
                    score += 0.1
                    break
            total_weight += 0.1
        
        # Normalize score
        return score / max(total_weight, 0.1)  # Avoid division by zero
    
    def _parse_filename_components(self, filename: str) -> Dict[str, Any]:
        """
        Parse a descriptive filename into semantic components.
        
        Args:
            filename: The filename to parse (without extension)
            
        Returns:
            Dictionary with semantic components
        """
        # Remove extension if present
        if '.' in filename:
            filename = filename.split('.')[0]
        
        # Initialize components
        components = {
            "character": "",
            "action": "",
            "setting": "",
            "details": []
        }
        
        # Handle special case for old naming format with "SingerYona" prefix
        if filename.lower().startswith("singeryona"):
            components["character"] = "yona"
            
            # Extract action from the rest of the filename
            if "guitar" in filename.lower():
                components["action"] = "guitar"
            elif "dance" in filename.lower():
                components["action"] = "dancing"
            elif "sing" in filename.lower():
                components["action"] = "singing"
                
            # Add the rest as details
            components["details"] = [filename]
            return components
        
        # Handle special case for runway_ prefix (old format)
        if filename.lower().startswith("runway_"):
            # These are usually generated clips, try to extract info from manual description
            components["details"] = [filename]
            return components
        
        # Split by underscores for the new descriptive format
        parts = filename.lower().replace(' ', '_').split('_')
        
        # Extract components based on position and content
        if parts and parts[0] in ["yona", "yonas"]:
            components["character"] = parts[0]
            parts = parts[1:]
        
        # Common actions in the dataset
        actions = ["guitar", "singing", "dancing", "skates", "playing", "pointing"]
        settings = ["neon", "city", "beach", "stage", "crowd", "friends"]
        
        # Assign parts to components
        for part in parts:
            if not components["action"] and part in actions:
                components["action"] = part
            elif not components["setting"] and part in settings:
                components["setting"] = part
            else:
                components["details"].append(part)
        
        # If we didn't find a character but the filename contains "yona"
        if not components["character"] and "yona" in filename.lower():
            components["character"] = "yona"
        
        return components
    
    def _find_matching_clip(self, description: str, used_clips: Dict[str, int] = None) -> Optional[Dict[str, Any]]:
        """
        Find a matching clip in the database based on the description.
        
        Args:
            description: Description of the scene
            used_clips: Dictionary tracking clip usage to enforce diversity
            
        Returns:
            Dictionary with clip metadata if found, None otherwise
        """
        try:
            from utils.supabase_client import get_supabase_client
            
            # Initialize used_clips if not provided
            if used_clips is None:
                used_clips = {}
            
            # Connect to Supabase
            supabase = get_supabase_client()
            
            # Parse the scene description into components
            scene_components = self._parse_scene_description(description)
            self.logger.info(f"Parsed scene components: {scene_components}")
            
            # Get all clips
            response = supabase.table("video_clips").select("*").execute()
            
            if not response.data or len(response.data) == 0:
                self.logger.warning("No clips found in database")
                return None
            
            # Process results to find the best match
            candidates = []
            
            for clip in response.data:
                clip_id = clip.get('id')
                
                # Calculate base score from component matching
                component_score = self._calculate_component_match_score(scene_components, clip)
                
                # Add bonus for manual description match if available
                manual_score = 0.0
                if clip.get('manual_description') and description:
                    manual_desc = clip.get('manual_description', '').lower()
                    desc_to_match = description.lower()
                    
                    # Count matching words
                    desc_words = set(desc_to_match.split())
                    manual_words = set(manual_desc.split())
                    matching_words = desc_words.intersection(manual_words)
                    
                    # Calculate a simple similarity score
                    if len(desc_words) > 0:
                        manual_score = len(matching_words) / len(desc_words)
                
                # Combine scores, prioritizing manual description if available
                if clip.get('manual_description'):
                    combined_score = max(manual_score, component_score)
                else:
                    combined_score = component_score
                
                # Apply diversity penalty based on previous usage
                usage_count = used_clips.get(clip_id, 0)
                diversity_penalty = min(usage_count * 0.15, 0.6)  # Max 60% penalty for repeated use
                
                # Calculate final score
                final_score = max(0.0, combined_score - diversity_penalty)
                
                # Only consider clips with a minimum score
                if final_score > 0.3:  # Minimum threshold
                    candidates.append({
                        'clip': clip,
                        'score': final_score,
                        'usage_count': usage_count
                    })
            
            # Sort candidates by score (descending)
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Return the best match if available
            if candidates:
                best_match = candidates[0]['clip']
                best_score = candidates[0]['score']
                self.logger.info(f"Found matching clip: {best_match['filename']} (score: {best_score:.2f})")
                return best_match
            
            # Fallback: Try direct keyword matching in filename
            try:
                # Extract key actions and settings from scene components
                key_terms = scene_components["actions"] + scene_components["settings"]
                
                if key_terms:
                    for term in key_terms:
                        if term in ['with', 'and', 'the']:
                            continue  # Skip common words
                            
                        response = supabase.table("video_clips").select("*").ilike("filename", f"%{term}%").execute()
                        
                        if response.data and len(response.data) > 0:
                            # Check if this clip has been used too many times
                            for clip in response.data:
                                clip_id = clip.get('id')
                                if used_clips.get(clip_id, 0) < 2:  # Limit to 2 uses per clip
                                    self.logger.info(f"Found clip with keyword '{term}' in filename: {clip['filename']}")
                                    return clip
            except Exception as e:
                self.logger.error(f"Error searching by filename: {str(e)}")
            
            # No match found
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding matching clip: {str(e)}")
            return None
    
    def _update_clip_usage(self, clip_id: str) -> None:
        """
        Update the usage statistics for a clip.
        
        Args:
            clip_id: UUID of the clip
        """
        try:
            from utils.supabase_client import get_supabase_client
            
            # Connect to Supabase
            supabase = get_supabase_client()
            
            # First get the current times_used value
            response = supabase.table("video_clips").select("times_used").eq("id", clip_id).execute()
            
            if response.data and len(response.data) > 0:
                current_times_used = response.data[0].get('times_used', 0)
                if current_times_used is None:
                    current_times_used = 0
                
                # Increment the counter
                new_times_used = current_times_used + 1
                
                # Update the times_used and last_used_at fields
                supabase.table("video_clips").update({
                    "times_used": new_times_used,
                    "last_used_at": "NOW()"
                }).eq("id", clip_id).execute()
                
                self.logger.info(f"Updated usage statistics for clip {clip_id} (used {new_times_used} times)")
            else:
                self.logger.warning(f"Could not find clip with ID {clip_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating clip usage: {str(e)}")
    
    def _index_new_clip(self, clip_path: str, prompt: str, description: str) -> Optional[str]:
        """
        Index a newly generated clip.
        
        Args:
            clip_path: Path to the clip file
            prompt: Text prompt used to generate the clip
            description: Description of the scene
            
        Returns:
            Clip ID if successful, None otherwise
        """
        try:
            # Get metadata
            filename = os.path.basename(clip_path)
            filepath = os.path.abspath(clip_path)
            filesize = os.path.getsize(clip_path)
            
            # Extract additional scene data if available
            scene_data = {}
            if isinstance(description, str) and hasattr(description, '_scene_data'):
                scene_data = getattr(description, '_scene_data', {})
            
            # Create a rich AI description using the prompt and scene data
            ai_description = prompt
            
            # Add camera motion if available
            if scene_data and 'camera_motion' in scene_data:
                ai_description += f", camera {scene_data.get('camera_motion')}"
                
            # Add start frame description if available
            if scene_data and 'start_frame_description' in scene_data:
                ai_description += f". Starting frame: {scene_data.get('start_frame_description')}"
                
            # Add end frame description if available
            if scene_data and 'end_frame_description' in scene_data:
                ai_description += f". Ending frame: {scene_data.get('end_frame_description')}"
            
            # Parse filename components
            filename_without_ext = os.path.splitext(filename)[0]
            components = self._parse_filename_components(filename_without_ext)
            
            # Create metadata from filename components
            filename_metadata = {
                "components": components,
                "character": components["character"],
                "action": components["action"],
                "setting": components["setting"],
                "details": components["details"]
            }
            
            # Connect to Supabase
            from utils.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            # Insert into database
            response = supabase.table("video_clips").insert({
                "filename": filename,
                "filepath": filepath,
                "filesize": filesize,
                "source_image": None,  # We don't track this yet
                "ai_description": ai_description,
                "manual_description": description,  # Use the scene description as manual description
                "scene_type": "generated",
                "filename_metadata": filename_metadata
            }).execute()
            
            self.logger.info(f"Indexed new clip: {filename}")
            
            # Return the clip ID if available
            if response.data and len(response.data) > 0:
                return response.data[0].get("id")
            return None
                
        except Exception as e:
            self.logger.error(f"Error indexing new clip: {str(e)}")
            return None
    
    def _generate_kling_clip(self, prompt: str, motion_prompt: Optional[str], duration: float, image_path: Optional[str] = None) -> str:
        """
        Generate a video clip using Kling AI API through PiAPI.
        
        Args:
            prompt: Text prompt describing the scene
            motion_prompt: Optional motion prompt for dynamic elements
            duration: Desired duration in seconds (may be limited by API)
            image_path: Path to an image to use as the base for video generation
            
        Returns:
            Path to the downloaded video clip
        """
        try:
            self.logger.info(f"Generating Kling AI clip with prompt: {prompt[:50]}...")
            
            # Import our custom Kling client and task manager
            from utils.kling_client import KlingAPIClient
            from utils.kling_task_manager import KlingTaskManager
            import requests
            import base64
            import uuid
            
            # Initialize the client and task manager
            client = KlingAPIClient(api_key=self.kling_api_key)
            task_manager = KlingTaskManager(client)
            
            # Prepare the image URL
            image_url = None
            if image_path:
                if os.path.isfile(image_path):
                    # For local files, we need to upload to a temporary hosting service
                    # Here we'll use ImgBB for simplicity
                    self.logger.info(f"Local image file detected: {image_path}")
                    
                    # Upload to ImgBB
                    image_url = self._upload_image_to_imgbb(image_path)
                    if not image_url:
                        self.logger.warning("Failed to upload image to ImgBB, using default image")
                        image_url = "https://framerusercontent.com/images/0vCKfdMyMxLCjtqWJ2bUQihEwk.png?scale-down-to=512"
                    
                    self.logger.info(f"Using image URL: {image_url}")
                elif image_path.startswith("http"):
                    # Use the provided URL directly
                    image_url = image_path
                    self.logger.info(f"Using provided image URL: {image_url}")
            
            # Enhance the prompt with anime style keywords
            anime_style_prompt = f"anime style, 2D cartoon animation, Japanese anime, {motion_prompt or prompt}"
            
            # Extract additional parameters from the scene if available
            scene_data = getattr(motion_prompt, '_scene_data', {}) if motion_prompt else {}
            
            # Default parameters
            aspect_ratio = "1:1"  # Default to square
            video_duration = 5    # Default to 5 seconds
            
            # Extract parameters from scene data if available
            if scene_data:
                if 'ratio' in scene_data:
                    # Convert from "1280:768" format to "16:9" format
                    if scene_data.get('ratio') == "1280:768" or scene_data.get('ratio') == "16:9":
                        aspect_ratio = "16:9"
                    elif scene_data.get('ratio') == "768:1280" or scene_data.get('ratio') == "9:16":
                        aspect_ratio = "9:16"
                
                if 'duration' in scene_data:
                    # Round to nearest supported duration (5 or 10)
                    try:
                        scene_duration = float(scene_data.get('duration'))
                        video_duration = 10 if scene_duration > 7.5 else 5
                    except (ValueError, TypeError):
                        self.logger.warning(f"Could not convert duration {scene_data.get('duration')} to float, using default of 5")
                        video_duration = 5
            
            # Create camera control parameters
            camera_control = {
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
            
            # Add camera motion if available
            if scene_data and 'camera_motion' in scene_data:
                motion = scene_data.get('camera_motion', '').lower()
                if 'zoom in' in motion:
                    camera_control["config"]["zoom"] = 10
                elif 'zoom out' in motion:
                    camera_control["config"]["zoom"] = -10
                elif 'pan left' in motion:
                    camera_control["config"]["pan"] = -10
                elif 'pan right' in motion:
                    camera_control["config"]["pan"] = 10
            
            # Create a task to generate a video
            self.logger.info("Creating video generation task...")
            task = task_manager.create_image_to_video(
                prompt=anime_style_prompt,
                negative_prompt="photorealistic, realistic, 3D, live action, real people, human faces, photorealism, realism",
                duration=video_duration,
                aspect_ratio=aspect_ratio,
                mode="std",
                cfg_scale=0.8,  # Slightly increased for better prompt adherence
                image_url=image_url,
                service_mode="public",
                camera_control=camera_control
            )
            
            if not task:
                raise Exception("Failed to create task: No response from API")
            
            self.logger.info(f"Task created with ID: {task['data']['task_id']}")
            
            # Wait for completion
            self.logger.info("Waiting for task completion...")
            result = task_manager.wait_for_completion(task['data']['task_id'])
            
            # Get video URL from the response
            output = result.get('data', {}).get('output', {})
            video_url = None
            
            # First try the direct video_url field
            if 'video_url' in output:
                video_url = output['video_url']
            # If not found, try to get it from the works array
            elif 'works' in output and output['works']:
                for work in output['works']:
                    if work.get('video', {}).get('resource_without_watermark'):
                        video_url = work['video']['resource_without_watermark']
                        break
                    elif work.get('video', {}).get('resource'):
                        video_url = work['video']['resource']
                        break
            
            if not video_url:
                raise Exception("No video URL found in the response")
            
            self.logger.info(f"Video available at: {video_url}")
            
            # Download the video
            timestamp = int(time.time())
            filename = f"data/raw_clips/kling_{timestamp}.mp4"
            
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"Video saved to: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Error generating video with Kling AI: {str(e)}")
            raise VideoGenerationError(f"Error generating video with Kling AI: {str(e)}")
    
    def _upload_image_to_imgbb(self, image_path: str) -> Optional[str]:
        """
        Upload an image to imgbb.com and return the URL.
        Ensures the image meets minimum size requirements.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            URL of the uploaded image, or None if upload failed
        """
        try:
            self.logger.info(f"Uploading image to imgbb: {image_path}")
            
            # Get ImgBB API key from environment
            imgbb_api_key = os.environ.get("IMGBB_API_KEY")
            if not imgbb_api_key:
                self.logger.warning("ImgBB API key not found in environment variables")
                return None
            
            # Import uuid and PIL
            import uuid
            from PIL import Image
            from utils.image_utils import resize_image
            
            # Check if the image meets minimum size requirements
            img = Image.open(image_path)
            width, height = img.size
            self.logger.info(f"Original image dimensions: {width}x{height} pixels")
            
            # If image is too small, resize it before uploading
            if width < 300 or height < 300:
                self.logger.info(f"Image is too small ({width}x{height}), resizing to meet minimum requirements")
                # Calculate scaling factors
                width_scale = 300 / width if width < 300 else 1
                height_scale = 300 / height if height < 300 else 1
                
                # Use the larger scaling factor to ensure both dimensions meet minimums
                scale = max(width_scale, height_scale)
                
                # Calculate new dimensions
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                self.logger.info(f"Resizing image to {new_width}x{new_height}")
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Save to a temporary file
                temp_path = f"{image_path}_resized.png"
                img.save(temp_path)
                image_path = temp_path
                self.logger.info(f"Saved resized image to {temp_path}")
            
            # Read the image file
            with open(image_path, "rb") as file:
                image_data = base64.b64encode(file.read()).decode('utf-8')
            
            # Prepare the payload
            payload = {
                "key": imgbb_api_key,
                "image": image_data,
                "name": f"yona_{uuid.uuid4().hex[:8]}"
            }
            
            # Upload to imgbb
            response = requests.post("https://api.imgbb.com/1/upload", data=payload)
            response.raise_for_status()
            
            # Extract the URL
            result = response.json()
            if result.get("success"):
                image_url = result["data"]["url"]
                self.logger.info(f"Image uploaded successfully: {image_url}")
                
                # Clean up temporary file if it was created
                if image_path.endswith("_resized.png") and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        self.logger.info(f"Removed temporary file: {image_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove temporary file: {str(e)}")
                
                # Verify the uploaded image meets size requirements
                from utils.image_utils import check_image_dimensions
                is_valid, width, height = check_image_dimensions(image_url)
                if not is_valid:
                    self.logger.warning(f"Uploaded image still doesn't meet size requirements. Using a default image.")
                    return "https://i.imgur.com/XqJZHVG.png"  # Default image that meets requirements
                
                return image_url
            else:
                self.logger.error(f"Failed to upload image: {result.get('error', {}).get('message', 'Unknown error')}")
                return None
        except Exception as e:
            self.logger.error(f"Error uploading image: {str(e)}")
            return None
