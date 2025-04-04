# AI Music Video Generator

An automated system that creates music videos for songs stored in a Supabase database. When a song's video_url is NULL, the system generates a video script using GPT, creates scenes using a video generation API, stitches the scenes with the song audio, and updates the database with the final video URL.

## Project Overview

This project implements an agent-based architecture for generating music videos:

1. **SongPollerAgent**: Polls the Supabase database for songs that need videos
2. **VideoScriptAgent**: Generates video scripts using OpenAI's GPT
3. **VideoGenAgent**: Creates video clips using AI video generation APIs
4. **StitcherAgent**: Combines video clips with audio
5. **UploaderAgent**: Uploads the final video and updates the database

## Setup

### Prerequisites

- Python 3.8+
- Supabase account with a songs table
- OpenAI API key
- Video generation API key (RunwayML, Pika Labs, or Suno)

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd ai-mv-generator
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your API keys:
   ```
   # Supabase Credentials
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key

   # OpenAI API Key
   OPENAI_API_KEY=your_openai_api_key

   # Video Generation API Keys (uncomment as needed)
   RUNWAYML_API_SECRET=your_runway_api_key  # Required for RunwayML video generation
   # PIKA_API_KEY=your_pika_api_key
   # MUSICAPI_KEY=your_suno_api_key
   ```

### Database Setup

Ensure your Supabase database has the following tables:

1. `songs` table with at least these fields:
   - `id` (UUID, primary key)
   - `title` (text)
   - `artist` (text)
   - `audio_url` (text)
   - `video_url` (text, nullable)
   - `params_used` (jsonb)
   - Other metadata fields (genre, mood, etc.)

2. `video_processing` table:
   ```sql
   CREATE TABLE video_processing (
       id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       song_id UUID NOT NULL REFERENCES songs(id),
       status TEXT NOT NULL DEFAULT 'pending',
       current_stage TEXT,
       script JSONB,
       error_message TEXT,
       retry_count INTEGER DEFAULT 0,
       processing_started_at TIMESTAMP WITH TIME ZONE,
       processing_completed_at TIMESTAMP WITH TIME ZONE,
       video_url TEXT,
       created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );

   CREATE INDEX video_processing_song_id_idx ON video_processing(song_id);
   CREATE INDEX video_processing_status_idx ON video_processing(status);
   ```

## Usage

### Running the Application

To start the application:

```
python main.py
```

This will:
1. Poll the Supabase database for songs without videos
2. Generate video scripts using GPT
3. Create video clips using the configured video generation API
4. Stitch the clips together with the song audio
5. Upload the final video
6. Update the database with the video URL

### Configuration

You can configure the application behavior in `utils/config.py`:

- `POLLING_INTERVAL`: Time between database polls (in seconds)
- `BATCH_SIZE`: Number of songs to process in one batch
- `MAX_RETRIES`: Maximum number of retry attempts for failed operations

## Project Structure

```
/ai-mv-generator
│
├── agents/
│   ├── song_poller.py      # Polls database for songs needing videos
│   ├── script_generator.py # Generates video scripts using GPT
│   ├── video_gen.py        # Generates video clips
│   ├── stitcher.py         # Combines clips with audio
│   └── uploader.py         # Uploads videos and updates database
│
├── utils/
│   ├── audio_tools.py      # Audio processing utilities
│   ├── supabase_client.py  # Supabase connection utilities
│   ├── config.py           # Configuration settings
│   ├── security.py         # Security utilities
│   └── error_handling.py   # Error handling utilities
│
├── data/
│   ├── raw_clips/          # Stores generated video clips
│   └── final_videos/       # Stores final stitched videos
│
├── main.py                 # Main application entry point
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables (not in repo)
```

## Customization

### Video Generation API

You can choose which video generation API to use by modifying the `api_provider` parameter in `main.py`:

```python
video_gen_agent = VideoGenAgent(api_provider="runway")  # Options: "runway", "pika", "suno"
```

### Upload Provider

You can choose where to upload the final videos by modifying the `upload_provider` parameter:

```python
uploader_agent = UploaderAgent(upload_provider="supabase")  # Options: "supabase", "youtube", "s3"
```

## License

[MIT License](LICENSE)
