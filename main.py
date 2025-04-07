import logging
import time
import os
from agents.song_poller import SongPollerAgent
from agents.script_generator import VideoScriptAgent
from agents.video_gen import VideoGenAgent
from agents.stitcher import StitcherAgent
from agents.uploader import UploaderAgent
from utils.config import POLLING_INTERVAL, BATCH_SIZE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def process_song(song_id: str, song_data: dict) -> None:
    """
    Process a single song through the entire pipeline.
    
    Args:
        song_id: UUID of the song to process
        song_data: Dictionary with song data
    """
    logger.info(f"Processing song: {song_data.get('title')} by Yona")
    
    # Initialize agents
    song_poller = SongPollerAgent()
    video_script_agent = VideoScriptAgent()
    video_gen_agent = VideoGenAgent(api_provider="runway")  # Change as needed
    stitcher_agent = StitcherAgent()
    uploader_agent = UploaderAgent(upload_provider="local")  # Using local Samba share
    
    try:
        # Create processing record
        processing_id = song_poller.create_processing_record(song_id)
        
        # Extract parameters for generation
        params = song_poller.extract_generation_params(song_data)
        
        # Update status to processing
        song_poller.update_processing_status(
            processing_id,
            "processing",
            current_stage="script_generation"
        )
        
        # Generate video script
        script = video_script_agent.generate_script(song_data["audio_url"], params)
        
        # Save script to processing record
        song_poller.update_processing_status(
            processing_id,
            "processing",
            current_stage="video_generation",
            script=script
        )
        
        # Generate video clips
        clips = video_gen_agent.generate_clips(script)
        
        # Update status
        song_poller.update_processing_status(
            processing_id,
            "processing",
            current_stage="video_stitching"
        )
        
        # Stitch video with audio
        final_video = stitcher_agent.stitch_video(clips, song_data["audio_url"])
        
        # Update status
        song_poller.update_processing_status(
            processing_id,
            "processing",
            current_stage="uploading"
        )
        
        # Upload video
        try:
            # Upload the video and get the URL (network path for local provider)
            video_url = uploader_agent.upload_video(final_video, {
                "title": song_data.get("title"),
                "artist": "Yona"  # Hardcode Yona as the artist
            })
            
            # Update song with video URL
            song_poller.update_video_url(song_id, video_url)
        except Exception as e:
            logger.error(f"Error uploading video: {str(e)}")
            raise
        
        # Update processing record
        song_poller.update_processing_status(
            processing_id,
            "completed",
            video_url=video_url
        )
        
        logger.info(f"Successfully processed song {song_id}")
        
    except Exception as e:
        logger.error(f"Error processing song {song_id}: {str(e)}")
        
        # Update processing record with error
        try:
            song_poller.update_processing_status(
                processing_id,
                "failed",
                error=str(e)
            )
        except Exception as update_error:
            logger.error(f"Error updating processing status: {str(update_error)}")

def main():
    """Main entry point for the application."""
    logger.info("Starting AI Music Video Generator")
    
    # Create necessary directories
    os.makedirs("data/raw_clips", exist_ok=True)
    os.makedirs("data/final_videos", exist_ok=True)
    
    song_poller = SongPollerAgent()
    
    while True:
        try:
            logger.info("Polling for songs that need videos...")
            
            # Get songs that need processing
            pending_songs = song_poller.get_pending_songs(limit=BATCH_SIZE)
            
            if not pending_songs:
                logger.info("No songs pending processing. Waiting...")
                time.sleep(POLLING_INTERVAL)
                continue
                
            logger.info(f"Found {len(pending_songs)} songs to process")
            
            # Process each song
            for song in pending_songs:
                process_song(song["id"], song)
            
            # Wait before next polling cycle
            time.sleep(POLLING_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    main()
