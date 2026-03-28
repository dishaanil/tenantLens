from google import genai
from google.genai import types
import os

client = genai.Client(
    vertexai=True,
    project="tenantlens",
    location="us-central1",
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: Vertex AI works",
)

print(response.text)