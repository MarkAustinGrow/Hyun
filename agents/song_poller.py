import logging
from typing import List, Dict, Any, Optional
from utils.supabase_client import get_supabase_client
from utils.config import BATCH_SIZE
from utils.error_handling import retry

class SongPollerAgent:
    def __init__(self):
        self.client = get_supabase_client()
        self.logger = logging.getLogger(__name__)
    
    @retry(max_attempts=3, initial_delay=2.0)
    def get_pending_songs(self, limit: int = BATCH_SIZE) -> List[Dict[str, Any]]:
        """
        Get songs that need video processing.
        
        Args:
            limit: Maximum number of songs to retrieve
            
        Returns:
            List of song dictionaries with relevant fields
        """
        try:
            # Get songs without videos - select columns that exist in the database
            response = self.client.table("songs") \
                .select("id, title, persona_id, audio_url, params_used, style, genre, mood, " \
                       "gpt_description, negative_tags, duration, image_url") \
                .is_("video_url", "null") \
                .limit(limit * 2) \
                .execute()
                
            songs = response.data
            
            # Get songs already in processing
            processing_response = self.client.table("video_processing") \
                .select("song_id") \
                .in_("status", ["pending", "processing", "retry"]) \
                .execute()
                
            processing_song_ids = [p["song_id"] for p in processing_response.data]
            
            # Filter songs not already in processing
            available_songs = [s for s in songs if s["id"] not in processing_song_ids]
            
            self.logger.info(f"Found {len(available_songs)} songs pending video generation")
            return available_songs[:limit]
            
        except Exception as e:
            self.logger.error(f"Error querying pending songs: {str(e)}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0)
    def create_processing_record(self, song_id: str) -> str:
        """
        Create a new video processing record.
        
        Args:
            song_id: UUID of the song
            
        Returns:
            UUID of the created processing record
        """
        try:
            response = self.client.table("video_processing") \
                .insert({"song_id": song_id, "status": "pending"}) \
                .execute()
                
            processing_id = response.data[0]["id"]
            self.logger.info(f"Created processing record {processing_id} for song {song_id}")
            return processing_id
            
        except Exception as e:
            self.logger.error(f"Error creating processing record: {str(e)}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0)
    def update_processing_status(self, processing_id: str, status: str, 
                               current_stage: Optional[str] = None, 
                               error: Optional[str] = None,
                               script: Optional[dict] = None, 
                               video_url: Optional[str] = None) -> None:
        """
        Update processing record status.
        
        Args:
            processing_id: UUID of the processing record
            status: New status (pending, processing, completed, failed, retry)
            current_stage: Current processing stage
            error: Error message if failed
            script: Generated script data
            video_url: Final video URL
        """
        try:
            update_data = {"status": status}
            
            if current_stage:
                update_data["current_stage"] = current_stage
                
            if error:
                update_data["error_message"] = error
                
            if script:
                update_data["script"] = script
                
            if video_url:
                update_data["video_url"] = video_url
                update_data["processing_completed_at"] = "NOW()"
                
            if status == "processing" and current_stage:
                # Check if processing_started_at is already set
                record = self.client.table("video_processing") \
                    .select("processing_started_at") \
                    .eq("id", processing_id) \
                    .execute() \
                    .data
                
                if record and not record[0]["processing_started_at"]:
                    update_data["processing_started_at"] = "NOW()"
                
            self.client.table("video_processing") \
                .update(update_data) \
                .eq("id", processing_id) \
                .execute()
                
            self.logger.info(f"Updated processing record {processing_id} status to {status}")
            
        except Exception as e:
            self.logger.error(f"Error updating processing status: {str(e)}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0)
    def update_video_url(self, song_id: str, video_url: str, network_path: Optional[str] = None) -> None:
        """
        Update the song with the generated video URL and optional network path.
        
        Args:
            song_id: UUID of the song
            video_url: URL to the generated video
            network_path: Optional network path for the video (for YouTube agent)
        """
        try:
            update_data = {"video_url": video_url}
            
            if network_path:
                update_data["network_path"] = network_path
                
            self.client.table("songs") \
                .update(update_data) \
                .eq("id", song_id) \
                .execute()
                
            self.logger.info(f"Updated song {song_id} with video URL: {video_url}")
            if network_path:
                self.logger.info(f"Updated song {song_id} with network path: {network_path}")
            
        except Exception as e:
            self.logger.error(f"Error updating video URL: {str(e)}")
            raise
    
    def extract_generation_params(self, song: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and combine parameters for video generation.
        
        Args:
            song: Song dictionary from database
            
        Returns:
            Dictionary of parameters for video generation
        """
        # Start with the params_used JSON if available
        params = song.get("params_used", {}) or {}
        
        # Add other relevant fields
        additional_params = {
            "title": song.get("title"),
            # Always use "Yona" as the artist
            "artist": "Yona",
            "style": song.get("style"),
            "genre": song.get("genre"),
            "mood": song.get("mood"),
            "description": song.get("gpt_description"),
            "negative_prompt": song.get("negative_tags"),  # Use negative_tags instead of negative_text
            "duration": song.get("duration"),
            "reference_image": song.get("image_url")
        }
        
        # Only add non-None values
        for key, value in additional_params.items():
            if value is not None:
                params[key] = value
                
        return params
