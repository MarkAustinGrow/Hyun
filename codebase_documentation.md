# AI Music Video Generator - Codebase Documentation

## Overview

The AI Music Video Generator is a system that automatically creates music videos for songs. It uses a combination of AI technologies:

1. **OpenAI GPT-4** for generating video scripts based on song metadata
2. **RunwayML** for generating video clips from the scripts
3. **Supabase** for storing song data and processing status

The system is designed to run as a continuous service that polls for songs that need videos, processes them through the pipeline, and updates the database with the results.

## System Architecture

The system follows a modular agent-based architecture:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │     │                 │
│  SongPoller     │────▶│  ScriptGenerator│────▶│  VideoGenerator │────▶│  Stitcher       │────▶│  Uploader       │
│  Agent          │     │  Agent          │     │  Agent          │     │  Agent          │     │  Agent          │
│                 │     │                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                                                                              │
        │                                                                                              │
        ▼                                                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                 │
│                                             Supabase Database                                                   │
│                                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **SongPollerAgent**: Polls the Supabase database for songs that need videos
2. **ScriptGeneratorAgent**: Generates video scripts using OpenAI GPT-4
3. **VideoGenAgent**: Generates video clips using RunwayML
4. **StitcherAgent**: Combines video clips with audio
5. **UploaderAgent**: Uploads the final video and updates the database

## Recent Fixes and Improvements

### 1. RunwayML Integration

We fixed several issues with the RunwayML integration:

#### Parameter Names
- Updated the code to use the correct parameter names for the RunwayML API:
  - `prompt_image` instead of `promptImage`
  - `prompt_text` instead of `promptText`
  - `ratio` instead of `resolution`

#### Image Format
- Implemented proper conversion of images to base64 data URIs:
  ```python
  data_uri = f"data:image/{image_type};base64,{base64_encoded}"
  ```
- Added detection of image type from URL extension

#### Response Handling
- Fixed how we extract the output URL from the API response
- The RunwayML API returns an array of URLs in the `output` field, not an object with a `url` property
- Updated the code to handle different possible output formats:
  ```python
  if isinstance(task_info.output, list) and len(task_info.output) > 0:
      video_url = task_info.output[0]
  ```

### 2. Supabase Query Fix

Fixed the Supabase query for finding songs without videos:
- Changed `.filter("video_url", "is", None)` to `.is_("video_url", "null")`
- This resolves the error: "unexpected 'o' expecting null or trilean value"

## How to Run the System

### Prerequisites

1. **Dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file with:
   ```
   RUNWAYML_API_SECRET=your_runway_api_key
   OPENAI_API_KEY=your_openai_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ```

3. **Supabase Database**:
   - Table: `songs`
     - Fields: `id`, `title`, `artist`, `audio_url`, `video_url`, etc.
   - Table: `video_processing`
     - Fields: `id`, `song_id`, `status`, `current_stage`, etc.

### Running the Full Application

```bash
python main.py
```

This will:
1. Poll for songs with `video_url = NULL`
2. Generate video scripts using OpenAI
3. Generate video clips using RunwayML
4. Stitch the clips with audio
5. Upload the final video
6. Update the database

### Testing the RunwayML Integration

For testing just the RunwayML integration without the full pipeline:

```bash
python test_video_gen.py
```

This will:
1. Generate a single video clip using RunwayML
2. Save it to `data/raw_clips/`

## API Notes

### RunwayML API

The RunwayML API expects:
- A base64-encoded data URI for the image
- A text prompt for the motion/description
- The output is an array of URLs to the generated videos

Example response:
```json
{
  "id": "d2e3d1f4-1b3c-4b5c-8d46-1c1d7ee86892",
  "status": "SUCCEEDED",
  "createdAt": "2024-06-27T19:49:32.335Z",
  "output": [
    "https://dnznrvs05pmza.cloudfront.net/output.mp4?_jwt=..."
  ]
}
```

**Important**: The output URLs are ephemeral and will expire within 24-48 hours.

## Next Steps

1. **Error Handling**: Improve error handling for edge cases
2. **Monitoring**: Add monitoring and alerting for the continuous service
3. **Performance**: Optimize the video generation process for better quality and efficiency
4. **UI**: Develop a user interface for managing the video generation queue
