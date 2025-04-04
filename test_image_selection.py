import os
from agents.video_gen import VideoGenAgent

def main():
    # Initialize the video generation agent
    video_gen = VideoGenAgent(api_provider="runway")
    
    # Test scenes with different descriptions
    test_scenes = [
        {
            "prompt": "Yona singing on stage",
            "description": "Close-up of Yona singing passionately into a microphone with neon lights in the background"
        },
        {
            "prompt": "Yona playing guitar",
            "description": "Yona playing guitar with a crowd of fans in the background"
        },
        {
            "prompt": "Yona skateboarding",
            "description": "Yona skateboarding down the street with bubblegum"
        },
        {
            "prompt": "Yona performing",
            "description": "Yona shouting into a microphone during an energetic performance"
        }
    ]
    
    print("Testing image selection for different scenes:")
    print("-" * 50)
    
    for i, scene in enumerate(test_scenes):
        print(f"\nScene {i+1}:")
        print(f"Prompt: {scene['prompt']}")
        print(f"Description: {scene['description']}")
        
        # Select an image for this scene
        image_path = video_gen.select_image_for_scene(scene['prompt'], scene['description'])
        
        print(f"Selected image: {os.path.basename(image_path)}")
        
        # Optionally, generate a video clip
        # Uncomment the following lines to test video generation
        # print("Generating video clip...")
        # clip_path = video_gen.generate_clip(
        #     prompt=scene['prompt'],
        #     motion_prompt=scene['description'],
        #     duration=4.0,
        #     image_path=image_path
        # )
        # print(f"Video clip generated: {clip_path}")
    
    print("\nImage selection test complete!")

if __name__ == "__main__":
    main()
