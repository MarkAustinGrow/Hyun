import logging
import json
import os
from typing import Dict, Any, Optional
import openai
from utils.config import OPENAI_API_KEY
from utils.error_handling import retry, circuit_breaker, ScriptGenerationError
from utils.security import get_api_key, validate_params

class VideoScriptAgent:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        api_key = get_api_key("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        openai.api_key = api_key
        
    @retry(max_attempts=3, initial_delay=2.0)
    @circuit_breaker(failure_threshold=5, reset_timeout=300.0)
    def generate_script(self, audio_url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a video script based on audio and parameters.
        
        Args:
            audio_url: URL to the audio file
            params: Dictionary containing generation parameters
                
        Returns:
            Dictionary containing:
            - scenes: List of scene descriptions with timestamps
            - metadata: Dict with mood, duration, bpm, etc.
            - prompts: Text prompts for each scene
        
        Raises:
            ScriptGenerationError: If script generation fails
        """
        try:
            # Validate required parameters
            required_fields = ["title"]  # Artist is now hardcoded as "Yona"
            if not validate_params(params, required_fields):
                raise ScriptGenerationError("Missing required parameters for script generation")
                
            # Ensure artist is set to "Yona"
            if "artist" not in params:
                params["artist"] = "Yona"
                
            # Define the function schema for OpenAI function calling
            functions = [{
                "name": "create_music_video_script",
                "description": "Create a scene-by-scene script for a music video",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metadata": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "artist": {"type": "string"},
                                "mood": {"type": "string"},
                                "bpm": {"type": "number"},
                                "duration": {"type": "number"}
                            },
                            "required": ["title", "artist", "mood"]
                        },
                        "scenes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_time": {"type": "number"},
                                    "end_time": {"type": "number"},
                                    "description": {"type": "string"},
                                    "prompt": {"type": "string"},
                                    "transition": {"type": "string"}
                                },
                                "required": ["start_time", "end_time", "description", "prompt"]
                            }
                        }
                    },
                    "required": ["metadata", "scenes"]
                }
            }]
            
            # Construct the system and user messages with anime focus
            system_message = "You are a creative anime music video director. Create a detailed scene-by-scene script for an anime-style music video featuring Yona, a cartoon K-pop star."
            
            # Build a detailed user message with all available parameters
            user_message = f"Create a music video script for the song '{params.get('title')}' by {params.get('artist')}.\n\n"
            
            # Add additional context if available
            if params.get('genre'):
                user_message += f"Genre: {params.get('genre')}\n"
            if params.get('mood'):
                user_message += f"Mood: {params.get('mood')}\n"
            if params.get('style'):
                user_message += f"Visual style: {params.get('style')}\n"
            if params.get('description'):
                user_message += f"Song description: {params.get('description')}\n"
            if params.get('duration'):
                user_message += f"Song duration: {params.get('duration')} seconds\n"
                
            # Add negative prompts if available
            if params.get('negative_prompt'):
                user_message += f"\nAvoid the following elements: {params.get('negative_prompt')}\n"
                
            # Add reference to audio and image if available
            user_message += f"\nAudio URL: {audio_url}\n"
            if params.get('reference_image'):
                user_message += f"Reference image: {params.get('reference_image')}\n"
                
            # Call the OpenAI API
            self.logger.info(f"Generating script for song: {params.get('title')} by {params.get('artist')}")
            
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                functions=functions,
                function_call={"name": "create_music_video_script"}
            )
            
            # Extract the function call arguments
            function_args = json.loads(response.choices[0].message.function_call.arguments)
            
            self.logger.info(f"Script generated with {len(function_args.get('scenes', []))} scenes")
            
            return function_args
            
        except openai.OpenAIError as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
            raise ScriptGenerationError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error generating script: {str(e)}")
            raise ScriptGenerationError(f"Error generating script: {str(e)}")
