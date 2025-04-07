import os
import logging
import argparse
from agents.uploader import UploaderAgent
from utils.config import VIDEO_SERVER, VIDEO_SERVER_USER, VIDEO_SERVER_PASSWORD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Test the local upload functionality."""
    parser = argparse.ArgumentParser(description="Test uploading a video to the Samba share")
    parser.add_argument("--video", required=True, help="Path to the video file to upload")
    parser.add_argument("--title", default="Test Video", help="Title for the video")
    args = parser.parse_args()
    
    # Verify the video file exists
    if not os.path.exists(args.video):
        logger.error(f"Video file not found: {args.video}")
        return
    
    # Verify environment variables
    if not VIDEO_SERVER_PASSWORD:
        logger.warning("VIDEO_SERVER_PASSWORD environment variable is not set")
        logger.warning("Make sure to set it in your .env file or provide it when prompted")
    
    logger.info(f"Testing upload to {VIDEO_SERVER} as {VIDEO_SERVER_USER}")
    
    # Create the uploader agent
    uploader = UploaderAgent(upload_provider="local")
    
    try:
        # Upload the video
        logger.info(f"Uploading {args.video}...")
        result = uploader._upload_to_local(args.video, {"title": args.title})
        
        # Display the results
        logger.info("Upload successful!")
        logger.info(f"Network path: {result['network_path']}")
        logger.info(f"HTTP URL: {result['http_url']} (for reference only)")
        
        logger.info("\nTo access the video:")
        logger.info(f"1. From Windows File Explorer: {result['network_path']}")
        logger.info(f"2. From a web browser (via Nginx): {result['http_url']}")
        logger.info(f"3. From inside Docker container: /mnt/videos/{os.path.basename(result['network_path'])}")
        
        logger.info("\nNote: The network path is now stored directly in the video_url field in the database.")
        
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")

if __name__ == "__main__":
    main()
