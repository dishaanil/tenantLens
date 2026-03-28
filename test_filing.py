import asyncio
import base64
from filing.agent import run

mock_payload = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "jsmith@abc.com",
    "phone": "9876543210",
    "address": "2386 VALENTINE AVENUE, #5A, BRONX",
    "preferred_language": "zh",
    "violation_type": "UNSANITARY CONDITION - MOLD",
    "open_violations": 40,
    "landlord_in_breach": True,
    "oldest_open_days": 8493,
    "tenant_rights": [
        "You have the right to a habitable apartment free from mold.",
        "Your landlord must correct Class C violations within 24 hours.",
        "You may file a 311 complaint to initiate an HPD inspection.",
        "You can withhold rent in escrow if your landlord fails to make repairs.",
    ],
    "form_payload": {
        "complaint_type": "UNSANITARY CONDITION",
        "descriptor": "MOLD",
        "address": "2386 VALENTINE AVENUE, #5A",
        "borough": "BRONX",
        "description": (
            "Tenant reports mold. Building has 26 open Class C and "
            "14 open Class B violations. Oldest open violation is 8493 days old. "
            "Landlord has not corrected conditions within legally required timeframe."
        ),
    },
}

print("--- Running narration + filing ---")
result = asyncio.run(run(mock_payload, tenant_confirmed=True))

# Save audio to file so we can listen to it
if result.get("audio_b64"):
    audio_bytes = base64.b64decode(result["audio_b64"])
    with open("narration_output.mp3", "wb") as f:
        f.write(audio_bytes)
    print(f"Audio saved to narration_output.mp3 ({len(audio_bytes)} bytes)")

print("Status:", result["status"])
print("Form review fields:", [f["label"] for f in result["form_review"]["fields"]])
