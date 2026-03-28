import asyncio
import base64
from filing.agent import run

mock_payload = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "jsmith@abc.com",
    "phone": "9876543210",
    "address": "2386 VALENTINE AVENUE",
    "violation_type": "mold",
    "open_violations": 50,
    "class_c_open": 26,
    "class_b_open": 14,
    "oldest_open_days": 8493,
    "aep_listed": False,
    "last_inspection": "2019-08-09T00:00:00.000",
    "landlord_in_breach": True,
    "tenant_rights": [
        "Landlord must correct Class C violations within 24 hours under NYC HMC §27-2017",
        "Landlord must correct Class B violations within 30 days under NYC HMC §27-2017",
        "Landlord cannot retaliate or evict within 6 months of a complaint",
        "As-is lease clauses do not override NYC Housing Maintenance Code",
        "Tenant may be eligible for rent reduction if violations go uncorrected",
    ],
    "form_payload": {
        "complaint_type": "UNSANITARY CONDITION",
        "descriptor": "MOLD",
        "address": "2386 VALENTINE AVENUE",
        "borough": "BRONX",
        "description": "Tenant reports mold. Building has 26 open Class C and 14 open Class B violations. Oldest open violation is 8493 days old. Landlord has not corrected conditions within legally required timeframe.",
    },
    "preferred_language": "en",
}

result = asyncio.run(run(mock_payload, tenant_confirmed=False))

print("status:", result["status"])
print("audio bytes length:", len(result["audio_b64"]))
print("form fields:", result["form_review"]["fields"])

# Save audio so you can listen to it (gTTS outputs MP3)
audio_bytes = base64.b64decode(result["audio_b64"])
with open("rights_narration.mp3", "wb") as f:
    f.write(audio_bytes)

print("Audio saved to rights_narration.mp3 — open it to verify narration")
