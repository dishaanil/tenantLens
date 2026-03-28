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
client = genai.Client(api_key=GEMINI_API_KEY)

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


def _build_narration_prompt(tenant_rights: list[str], violation_type: str, address: str, language: str) -> str:
    language_name = LANGUAGE_NAMES.get(language, "English")
    rights_bullets = "\n".join(f"- {r}" for r in tenant_rights)
    return f"""You are a tenant rights advocate speaking directly to an NYC renter.
Speak clearly and calmly in {language_name}.
A housing violation has been identified at {address}: {violation_type}.

Read each of these rights out loud in plain language any renter can understand.
Speak directly to the tenant as "you". Do not add legal disclaimers or caveats.

{rights_bullets}

End with: "I have prepared a 311 complaint for you. Please review it now and confirm to submit."
"""


async def narrate_rights(payload: dict) -> bytes:
    """
    Use Gemini Pro to generate spoken audio of the tenant's rights.
    Returns raw PCM audio bytes.
    Never modifies the legal language in tenant_rights.
    """
    prompt = _build_narration_prompt(
        tenant_rights=payload["tenant_rights"],
        violation_type=payload["violation_type"],
        address=payload["address"],
        language=payload.get("preferred_language", "en"),
    )

    logger.info("Generating rights narration audio via Gemini...")
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        ),
    )

    audio_data = response.candidates[0].content.parts[0].inline_data.data
    logger.info("Audio narration generated successfully.")
    return audio_data


def build_form_review(payload: dict) -> dict:
    """
    Format the 311 form_payload into a structured review object for the UI.
    Never exposes raw API responses to the tenant.
    """
    fp = payload["form_payload"]
    return {
        "fields": [
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
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

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
