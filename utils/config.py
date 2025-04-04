import os
from dotenv import load_dotenv

load_dotenv()

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# OpenAI config
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# YouTube config
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
YOUTUBE_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID")

# Music API config
MUSICAPI_KEY = os.environ.get("MUSICAPI_KEY")
SONOTELLER_API_KEY = os.environ.get("SONOTELLER_API_KEY")

# Processing config
MAX_RETRIES = 3
POLLING_INTERVAL = 300  # seconds
BATCH_SIZE = 5  # number of songs to process in one batch
