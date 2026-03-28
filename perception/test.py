from google import genai

client = genai.Client(
    vertexai=True,
    project="tenantlens",
    location="global",
)

response = client.models.generate_content(
    model="gemini-3.1-flash-lite-preview",
    contents="Say hello from TenantLens"
)

print(response.text)