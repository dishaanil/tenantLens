"""
gemini_vision.py
Perception Agent — Step 2
Sends a base64 JPEG frame to Gemini and returns raw structured text.
Client config mirrors test.py exactly.
"""
 
import os
import base64
from google import genai
from google.genai import types
from dotenv import load_dotenv
 
load_dotenv()
 
# Mirrors test.py exactly
client = genai.Client(
    vertexai=True,
    project="tenantlens",
    location="global",
)
 
MODEL = "gemini-3.1-flash-lite-preview"
 
VIOLATION_PROMPT = """
You are a housing inspector AI analyzing an image from a tenant's phone camera.
 
The image may show:
- A direct photo of a housing condition
- A phone screen displaying a photo of a housing condition
Analyze whatever is visible in the image.
 
Identify any of the following housing conditions:
- mold (black, green, or white growth on walls, ceilings, surfaces)
- water_damage (stains, peeling paint, damp patches, discoloration)
- pest_damage (droppings, gnaw marks, nests, bite marks on surfaces)
- pest_infestation (cockroaches, rodents, bedbugs, ants, or visible evidence)
- broken_fixture (broken windows, doors, locks, plumbing)
- structural_damage (cracks in walls, ceiling damage, deteriorating floors)
- heating_issue (damage to heating units, blocked vents)
 
If you see droppings, gnaw marks, or rodent evidence — classify as pest_damage.
If you see live insects or rodents — classify as pest_infestation.
 
Respond in EXACTLY this format — no other text:
VIOLATION: <mold | water_damage | pest_damage | pest_infestation | broken_fixture | structural_damage | heating_issue | none>
CONFIDENCE: <high | medium | low>
DESCRIPTION: <one sentence describing exactly what you see that indicates the violation>
""".strip()
 
 
def analyze_frame(frame_base64: str) -> str:
    """
    Send a base64-encoded JPEG to Gemini via Vertex AI.
    Returns raw response text — parsing handled by violation_parser.py.
    """
    image_bytes = base64.b64decode(frame_base64)
 
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text=VIOLATION_PROMPT),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/jpeg",
                            data=image_bytes,
                        )
                    ),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=150,
        ),
    )
    return response.text.strip()
 
 
if __name__ == "__main__":
    # Test using REAL camera frame — not a blank black image
    from camera_feed import get_frame_base64
 
    print(f"Capturing real frame and sending to {MODEL}...")
    frame_b64 = get_frame_base64()
    print(f"Frame captured — base64 length: {len(frame_b64)}")
 
    raw = analyze_frame(frame_b64)
    print("\nGemini response:")
    print(raw)
    print("\ngemini_vision.py OK")
 