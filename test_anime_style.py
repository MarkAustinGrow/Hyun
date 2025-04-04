import os
from agents.video_gen import VideoGenAgent

def main():
    # Initialize the video generation agent
    video_gen = VideoGenAgent(api_provider="runway")
    
    # Test scene with anime-specific prompt
    test_scene = {
        "prompt": "Yona singing on stage with anime style",
        "description": "Close-up of anime character Yona singing passionately into a microphone with neon lights in the background, 2D animation style"
    }
    
    print("Testing anime-style video generation:")
    print("-" * 50)
    
    print(f"\nScene:")
    print(f"Prompt: {test_scene['prompt']}")
    print(f"Description: {test_scene['description']}")
    
    # Select an image for this scene
    image_path = video_gen.select_image_for_scene(test_scene['prompt'], test_scene['description'])
    
    print(f"Selected image: {os.path.basename(image_path)}")
    
    # Generate a video clip with the enhanced anime style
    print("Generating video clip with enhanced anime style...")
    clip_path = video_gen.generate_clip(
        prompt=test_scene['prompt'],
        motion_prompt=test_scene['description'],
        duration=4.0,
        image_path=image_path
    )
    
    print(f"Video clip generated: {clip_path}")
    print(f"Full path: {os.path.abspath(clip_path)}")
    
    print("\nTest complete! Check the generated video to see if it maintains an anime style.")

if __name__ == "__main__":
    main()
