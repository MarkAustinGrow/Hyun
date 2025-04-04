# 🎮 AI Music Video Generator Roadmap

## 🧠 Project Vision

Build a fully automated agentic system that creates music videos for songs stored in a Supabase database. When a song's video_url is NULL, the system generates a video script using GPT, creates scenes using a video generation API, stitches the scenes with the song audio, and updates the database with the final video URL.

## 🔍 Phase 0: Research & Design

### 0.1 System Architecture
- Define overall system architecture and data flow
- Create architecture diagrams and component relationships
- Establish API contracts between agents
- Define data schemas for inter-agent communication

### 0.2 Technology Evaluation
- Evaluate and select video generation APIs (RunwayML/Pika Labs/Suno Gen-2)
- Compare capabilities, costs, and limitations
- Research optimal video stitching approaches
- Identify potential technical challenges and solutions

### 0.3 Prototype Key Algorithms
- Create proof-of-concept for video script generation
- Test basic video generation with selected APIs
- Prototype video stitching approach
- Establish performance metrics and success criteria

## ✅ Phase 1: Setup & Infrastructure

### 1.1 Project Environment
- Set up Python virtual environment
- Install required dependencies
- Create project folder structure following the recommended organization
- Set up configuration files (.env for API keys and credentials)

### 1.2 Supabase Integration
- Set up Supabase client with supabase-py
- Configure database connection
- Create utility functions for database operations
- Test connection and basic CRUD operations

### 1.3 Security Implementation
- Implement secure storage of API keys and credentials
- Set up environment variable management
- Configure rate limiting to prevent API abuse
- Establish proper permissions for storage access

## 🧠 Phase 2: Agent Development

### 2.1 Database Agents (First Priority)
#### 2.1.1 SongPollerAgent
- Implement connection to Supabase songs table
- Create function to query rows where video_url = NULL
- Extract audio_url and params_used from results
- Set up polling mechanism (either cron job or long-running worker)
- Add logging and error handling

#### 2.1.2 UploaderAgent
- Implement upload functionality to Supabase Storage or S3
- Generate public video_url for the uploaded video
- Create function to update the song's row in the database
- Add verification to ensure the video is accessible

### 2.2 Content Generation Agents (Second Priority)
#### 2.2.1 VideoScriptAgent
- Set up OpenAI API integration with function calling
- Design prompt templates for script generation
- Implement function to send params_used and audio_url to ChatGPT
- Parse and validate returned scene-by-scene video script
- Extract metadata (mood, duration, bpm)
- Add error handling for API failures
- Create unit tests for script validation

#### 2.2.2 VideoGenAgent
- Implement integration with selected video generation API
- Create function to send scene prompts to the API
- Handle API responses and download generated video clips
- Implement retry logic for failed generations
- Store clips in the raw_clips directory
- Add circuit breakers for API call protection

### 2.3 Media Processing Agents (Final Priority)
#### 2.3.1 StitcherAgent
- Set up MoviePy or FFmpeg wrapper
- Implement functions to align clips according to script timing
- Add audio synchronization with the original audio_url
- Create overlay functionality for text and transitions
- Export the final compiled video to the final_videos directory
- Implement error handling for processing failures

## 🚀 Phase 2.5: MVP Implementation

### 2.5.1 Simplified Pipeline
- Create a minimal end-to-end pipeline connecting all agents
- Implement basic error handling
- Focus on core functionality without advanced features

### 2.5.2 Initial Testing
- Test with a single song and basic parameters
- Validate core functionality before adding complexity
- Identify and fix critical issues

## 🔧 Phase 3: Orchestration & Automation

### 3.1 main.py
- Implement the full orchestrator flow as outlined in the pseudocode
- Create robust pipeline to connect all agents
- Add comprehensive error handling and recovery mechanisms:
  - Circuit breakers for external API calls
  - Robust retry strategy with exponential backoff
  - Dead-letter queue for failed processing attempts
  - Transaction management to prevent partial updates
- Implement logging throughout the process
- Create notification system for successful/failed video generations

### 3.2 Scheduling
- Set up automated scheduling system
- Implement either cron jobs or a long-running worker
- Add monitoring for the automated process
- Create dashboard or reporting mechanism

## 🔬 Phase 4: Testing & Scaling

### 4.1 Comprehensive Testing
- Expand unit tests for each agent
- Implement integration tests for the full pipeline
- Create end-to-end system tests
- Test with various audio inputs and parameters
- Develop error scenarios and recovery tests
- Perform load testing and stress testing

### 4.2 Optimization
- Profile performance and identify bottlenecks
- Implement caching strategies where appropriate
- Optimize API usage to minimize costs
- Add parallel processing for multiple songs
- Refine error handling based on production patterns

## 🧱 Folder Structure

```bash
/ai-mv-generator
│
├── design/                # New folder for design documents
│   ├── architecture.md
│   └── api_contracts.md
│
├── agents/
│   ├── song_poller.py
│   ├── script_generator.py
│   ├── video_gen.py
│   ├── stitcher.py
│   └── uploader.py
│
├── utils/
│   ├── audio_tools.py
│   ├── supabase_client.py
│   ├── config.py
│   ├── security.py        # New file for security utilities
│   └── error_handling.py  # New file for error handling utilities
│
├── data/
│   ├── raw_clips/
│   └── final_videos/
│
├── tests/                 # Expanded test directory
│   ├── unit/
│   ├── integration/
│   └── system/
│
├── main.py                # Orchestrates everything
└── .env                   # Supabase keys, API keys, paths
```

## 🔧 Toolbox

| Function | Tool Recommendation |
|----------|---------------------|
| DB Handling | supabase-py |
| GPT-4 Access | openai package (w/ function calling) |
| Video Gen API | Runway, Pika, Suno, AnimateDiff |
| Clip Assembly | moviepy, ffmpeg-python |
| Prompt Templates | Stored in prompt_templates/ |
| Deployment | Docker or local with virtualenv |
| Error Handling | tenacity for retries, circuit-breaker pattern |
| Security | python-dotenv, pydantic for validation |
