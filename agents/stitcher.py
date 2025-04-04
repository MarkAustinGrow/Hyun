import logging
import os
import time
import tempfile
import requests
import subprocess
from typing import List, Dict, Any, Optional
from utils.error_handling import retry, VideoStitchingError

class StitcherAgent:
    def __init__(self):
        """
        Initialize the StitcherAgent.
        """
        self.logger = logging.getLogger(__name__)
        
        # Create output directory if it doesn't exist
        os.makedirs("data/final_videos", exist_ok=True)
    
    def _download_audio(self, audio_url: str) -> str:
        """
        Download audio from URL to a temporary file.
        
        Args:
            audio_url: URL to the audio file
            
        Returns:
            Path to the downloaded audio file
        """
        self.logger.info(f"Downloading audio from: {audio_url}")
        
        # Create a temporary file
        audio_path = os.path.join(tempfile.gettempdir(), f"audio_{int(time.time())}.mp3")
        
        # Download the audio file
        response = requests.get(audio_url, stream=True)
        response.raise_for_status()
        
        with open(audio_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        self.logger.info(f"Audio downloaded to: {audio_path}")
        return audio_path
    
    @retry(max_attempts=2, initial_delay=2.0)
    def stitch_video(self, clips: List[Dict[str, Any]], audio_url: str, 
                    output_filename: Optional[str] = None) -> str:
        """
        Stitch together video clips with audio.
        
        Args:
            clips: List of dictionaries with clip information
            audio_url: URL to the audio file
            output_filename: Optional custom filename for the output video
            
        Returns:
            Path to the final stitched video
            
        Raises:
            VideoStitchingError: If video stitching fails
        """
        try:
            self.logger.info(f"Stitching {len(clips)} clips with audio: {audio_url}")
            
            # Filter out clips with errors
            valid_clips = [clip for clip in clips if clip.get("clip_path") and os.path.exists(clip.get("clip_path"))]
            
            if not valid_clips:
                raise VideoStitchingError("No valid clips to stitch")
                
            self.logger.info(f"Found {len(valid_clips)} valid clips for stitching")
            
            # Sort clips by start_time
            valid_clips.sort(key=lambda x: x.get("start_time", 0))
            
            # Generate output filename if not provided
            if not output_filename:
                timestamp = int(time.time())
                output_filename = f"data/final_videos/final_{timestamp}.mp4"
            
            # Download the audio file
            audio_path = self._download_audio(audio_url)
            
            # Use FFmpeg to stitch the clips together
            self._stitch_with_ffmpeg(valid_clips, audio_path, output_filename)
            
            # Clean up the temporary audio file
            try:
                os.remove(audio_path)
            except:
                pass
                
            self.logger.info(f"Successfully stitched video: {output_filename}")
            
            return output_filename
            
        except Exception as e:
            self.logger.error(f"Error stitching video: {str(e)}")
            raise VideoStitchingError(f"Error stitching video: {str(e)}")
    
    def _stitch_with_ffmpeg(self, clips: List[Dict[str, Any]], audio_path: str, output_filename: str) -> None:
        """
        Stitch video clips together using FFmpeg.
        
        Args:
            clips: List of dictionaries with clip information
            audio_path: Path to the audio file
            output_filename: Path to the output video file
        """
        self.logger.info("Stitching video clips with FFmpeg...")
        
        # Create a temporary file list for FFmpeg
        file_list_path = os.path.join(tempfile.gettempdir(), "temp_file_list.txt")
        
        try:
            # Write the file list
            with open(file_list_path, "w") as f:
                for clip_info in clips:
                    clip_path = clip_info.get("clip_path")
                    if clip_path and os.path.exists(clip_path):
                        # Use absolute path to avoid issues
                        abs_path = os.path.abspath(clip_path)
                        # Escape single quotes in the path
                        escaped_path = abs_path.replace("'", "'\\''")
                        f.write(f"file '{escaped_path}'\n")
            
            self.logger.info(f"Created file list with {len(clips)} clips")
            
            # Create a temporary output file for the concatenated video
            concat_output = os.path.join(tempfile.gettempdir(), f"concat_{int(time.time())}.mp4")
            
            # Step 1: Concatenate the video clips
            self.logger.info("Concatenating video clips...")
            subprocess.run([
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", file_list_path,
                "-c", "copy",
                concat_output
            ], check=True, capture_output=True)
            
            # Step 2: Add the audio to the concatenated video
            self.logger.info("Adding audio track...")
            subprocess.run([
                "ffmpeg",
                "-i", concat_output,
                "-i", audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_filename
            ], check=True, capture_output=True)
            
            self.logger.info("Video stitching complete")
            
            # Clean up temporary files
            os.remove(file_list_path)
            os.remove(concat_output)
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            raise VideoStitchingError(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            self.logger.error(f"Error in FFmpeg processing: {str(e)}")
            raise VideoStitchingError(f"Error in FFmpeg processing: {str(e)}")
        finally:
            # Clean up temporary files
            if os.path.exists(file_list_path):
                try:
                    os.remove(file_list_path)
                except:
                    pass
            
            if os.path.exists(concat_output):
                try:
                    os.remove(concat_output)
                except:
                    pass
    
    def _placeholder_stitch(self, clips: List[Dict[str, Any]], audio_url: str, output_filename: str) -> None:
        """
        Placeholder implementation for video stitching.
        
        In a real implementation, this would use MoviePy or FFmpeg to stitch the clips together.
        """
        # Simulate processing time
        time.sleep(3)
        
        # Create a placeholder output file
        with open(output_filename, "w") as f:
            f.write(f"Placeholder for stitched video with {len(clips)} clips and audio: {audio_url}\n\n")
            
            # Add information about each clip
            for i, clip in enumerate(clips):
                f.write(f"Clip {i+1}:\n")
                f.write(f"  Path: {clip.get('clip_path')}\n")
                f.write(f"  Start time: {clip.get('start_time')}\n")
                f.write(f"  End time: {clip.get('end_time')}\n")
                f.write(f"  Prompt: {clip.get('prompt')[:50]}...\n\n")
