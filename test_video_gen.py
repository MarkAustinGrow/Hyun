import logging
import os
from agents.video_gen import VideoGenAgent

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create necessary directories
os.makedirs("data/raw_clips", exist_ok=True)
os.makedirs("data/final_videos", exist_ok=True)

# Test data
test_prompt = "A serene mountain landscape with a flowing river"
test_motion_prompt = "Camera slowly pans from left to right, revealing more of the landscape"
test_image_url = "https://framerusercontent.com/images/0vCKfdMyMxLCjtqWJ2bUQihEwk.png?scale-down-to=512"

# Initialize the video generation agent
video_gen = VideoGenAgent(api_provider="runway")

# Generate a test clip
try:
    print("Starting video generation with RunwayML...")
    clip_path = video_gen.generate_clip(
        prompt=test_prompt,
        motion_prompt=test_motion_prompt,
        duration=5.0,
        image_url=test_image_url
    )
    print(f"Successfully generated clip: {clip_path}")
    print(f"You can find the video at: {os.path.abspath(clip_path)}")
except Exception as e:
    print(f"Error generating clip: {str(e)}")
