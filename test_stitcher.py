import os
import glob
from agents.stitcher import StitcherAgent

def main():
    # Initialize the stitcher agent
    stitcher = StitcherAgent()
    
    # Get all MP4 files in the raw_clips directory
    clip_files = glob.glob("data/raw_clips/runway_*.mp4")
    
    # Sort them by creation time (newest first)
    clip_files.sort(key=os.path.getmtime, reverse=True)
    
    # Take the 8 most recent clips
    recent_clips = clip_files[:8]
    
    print(f"Found {len(recent_clips)} clips to stitch")
    for i, clip in enumerate(recent_clips):
        print(f"Clip {i+1}: {clip}")
    
    # Create clip info dictionaries
    clips = []
    for i, clip_path in enumerate(recent_clips):
        clips.append({
            "clip_path": clip_path,
            "start_time": i * 4,  # 4 seconds per clip
            "end_time": (i + 1) * 4,
            "prompt": f"Test clip {i+1}"
        })
    
    # Audio URL - use one from a previous successful run
    audio_url = "https://cdn1.suno.ai/4d6e0241-ee04-4cba-bb0a-db282fdd81ac.mp3"
    
    # Stitch the video
    output_path = stitcher.stitch_video(clips, audio_url)
    
    print(f"Video stitched successfully: {output_path}")
    print(f"Full path: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
