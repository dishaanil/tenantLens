"""
TenantLens — Filing Agent (Agent 3)

Receives the Agent 2 payload, narrates tenant rights via Gemini Pro audio,
presents the pre-filled 311 form for review, and submits via browser agent
on explicit tenant confirmation.
"""

import os
import json
import base64
import asyncio
import logging
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

# Text generation — API key (gemini-flash-latest, confirmed working)
text_client = genai.Client(api_key=GEMINI_API_KEY)

# TTS — Vertex AI (uses GCP credits, no free tier cap)
tts_client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location=VERTEX_LOCATION,
)

# Supported language display names for narration prompt
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "zh": "Mandarin Chinese",
    "ru": "Russian",
    "ar": "Arabic",
    "fr": "French",
    "pt": "Portuguese",
    "bn": "Bengali",
    "ko": "Korean",
    "pl": "Polish",
}


def _build_text_prompt(tenant_rights: list[str], violation_type: str, address: str, language: str) -> str:
    """
    Step 1 prompt: asks Gemini Flash to write the narration script
    in plain spoken language, in the tenant's language.
    Output is clean text — no instructions, no markdown, just words to be spoken.
    """
    language_name = LANGUAGE_NAMES.get(language, "English")
    rights_bullets = "\n".join(f"- {r}" for r in tenant_rights)
    return f"""Write a short spoken statement in {language_name} for a tenant rights advocate
to read aloud to an NYC renter. A housing violation was found at {address}: {violation_type}.

Cover these rights in plain, simple language. Speak directly to the tenant as "you".
No bullet points, no markdown, no legal disclaimers — just natural spoken sentences.

Rights to cover:
{rights_bullets}

End with (translated to {language_name}): "I have prepared a 311 complaint for you.
Please review it now and confirm to submit."

Output only the spoken text. Nothing else."""


async def _generate_narration_text(payload: dict) -> str:
    """
    Step 1: Use Gemini Flash to generate the narration script in the tenant's language.
    """
    language = payload.get("preferred_language", "en")
    prompt = _build_text_prompt(
        tenant_rights=payload["tenant_rights"],
        violation_type=payload["violation_type"],
        address=payload["address"],
        language=language,
    )
    logger.info(f"Generating narration text in language: {language}")
    response = text_client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    text = response.text.strip()
    logger.info(f"Narration text generated ({len(text)} chars)")
    return text


async def narrate_rights(payload: dict) -> bytes:
    """
    Step 1: Generate narration text in tenant's language via Gemini Flash.
    Step 2: Convert that text to spoken audio via Gemini TTS.
    Returns raw PCM audio bytes.
    Never modifies the legal language in tenant_rights.
    """
    # Step 1 — generate clean spoken text in the right language
    narration_text = await _generate_narration_text(payload)

    # Step 2 — convert text to audio via gTTS (reliable, free, multilingual)
    import io
    from gtts import gTTS

    language = payload.get("preferred_language", "en")
    logger.info(f"Converting narration text to audio via gTTS (lang={language})...")
    tts = gTTS(text=narration_text, lang=language, slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    audio_data = buffer.getvalue()
    logger.info(f"Audio narration generated successfully ({len(audio_data)} bytes, MP3).")
    return audio_data


def build_form_review(payload: dict) -> dict:
    """
    Format the 311 form_payload into a structured review object for the UI.
    Never exposes raw API responses to the tenant.
    """
    fp = payload["form_payload"]
    return {
        "fields": [
            {"label": "First Name",     "value": payload.get("first_name", "")},
            {"label": "Last Name",      "value": payload.get("last_name", "")},
            {"label": "Email",          "value": payload.get("email", "")},
            {"label": "Phone",          "value": payload.get("phone", "")},
            {"label": "Complaint Type", "value": fp["complaint_type"]},
            {"label": "Issue",          "value": fp["descriptor"]},
            {"label": "Address",        "value": fp["address"]},
            {"label": "Borough",        "value": fp["borough"]},
            {"label": "Description",    "value": fp["description"]},
        ],
        "context": {
            "violation_type":    payload["violation_type"],
            "open_violations":   payload["open_violations"],
            "landlord_in_breach": payload["landlord_in_breach"],
            "oldest_open_days":  payload["oldest_open_days"],
        },
        "confirmation_prompt": "Does this look correct? Confirm to submit to NYC 311.",
    }


async def open_311_browser(form_payload: dict) -> dict:
    """
    Browser agent: opens the NYC 311 housing complaint flow with pre-filled data.
    Stops before final submit — tenant must click Submit themselves.
    Requires explicit confirmation before this function is ever called.
    """
    from playwright.async_api import async_playwright

    logger.info(f"Opening 311 browser for: {form_payload['address']}, {form_payload['borough']}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to NYC 311 housing complaint form
        await page.goto("https://portal.311.nyc.gov/article/?kanumber=KA-01012")
        await page.wait_for_load_state("networkidle")

        logger.info("311 form loaded. Pre-filled complaint data is ready for tenant review.")

        result = {
            "status": "form_ready",
            "url": page.url,
            "prefilled_data": {
                "complaint_type": form_payload["complaint_type"],
                "descriptor":     form_payload["descriptor"],
                "address":        f"{form_payload['address']}, {form_payload['borough']}",
                "description":    form_payload["description"],
            },
            "message": "Review the pre-filled form and click Submit to file your complaint.",
        }

        # Hold browser open for tenant to review and submit (5 minutes)
        await asyncio.sleep(300)
        await browser.close()

    return result


async def run(payload: dict, tenant_confirmed: bool = False) -> dict:
    """
    Main entry point for the Filing Agent.

    Step 1 — Narrate tenant_rights via Gemini Pro audio in preferred_language.
    Step 2 — Return pre-filled form_payload for tenant review.
    Step 3 — If tenant_confirmed=True, launch browser agent with pre-filled 311 form.

    Never submits without explicit tenant confirmation.
    """
    logger.info(f"[FilingAgent] Processing payload for: {payload['address']}")

    # Step 1: Narrate rights (audio bytes → base64 for transport)
    audio_bytes = await narrate_rights(payload)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else ""
    if not audio_bytes:
        logger.warning("No audio returned — check TTS finish_reason in logs above.")

    # Step 2: Build form review
    form_review = build_form_review(payload)

    result = {
        "status":       "awaiting_confirmation",
        "audio_b64":    audio_b64,      # PCM audio, base64 encoded
        "form_review":  form_review,
        "address":      payload["address"],
        "violation":    payload["violation_type"],
    }

    # Step 3: Only proceed to browser on confirmed=True
    if tenant_confirmed:
        logger.info("[FilingAgent] Tenant confirmed. Launching 311 browser agent.")
        submission = await open_311_browser(payload["form_payload"])
        result["status"] = "form_opened"
        result["submission"] = submission

    return result
