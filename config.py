import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "global")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite-preview")