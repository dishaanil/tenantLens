"""
TenantLens — Filing Agent (Agent 3)

Receives the Agent 2 payload, narrates tenant rights via Gemini Pro audio,
presents the pre-filled 311 form for review, and submits via browser agent
on explicit tenant confirmation.
"""

import os
import re
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

# Text generation — API key (used for narration script)
text_client = genai.Client(api_key=GEMINI_API_KEY)

# TTS — Vertex AI regional (used for audio generation)
tts_client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location=VERTEX_LOCATION,
)

# Form filling — Vertex AI global (uses GCP credits, bypasses free tier quota)
form_client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location="global",
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


def _parse_address(raw_address: str) -> tuple[str, str]:
    """
    Split a combined address string into (street_address, apt_number).
    Handles patterns like:
      "2386 VALENTINE AVE APT 4B"   → ("2386 VALENTINE AVE", "4B")
      "2386 VALENTINE AVE UNIT 2C"  → ("2386 VALENTINE AVE", "2C")
      "2386 VALENTINE AVE #3"       → ("2386 VALENTINE AVE", "3")
      "2386 VALENTINE AVE"          → ("2386 VALENTINE AVE", "")
    """
    pattern = re.compile(
        r"^(.*?)\s*(?:APT\.?|APARTMENT|UNIT|STE\.?|SUITE|#)\s*([A-Z0-9\-]+)\s*$",
        re.IGNORECASE,
    )
    m = pattern.search(raw_address.strip())
    if m:
        return m.group(1).strip().rstrip(",").strip(), m.group(2).strip()
    return raw_address.strip().rstrip(",").strip(), ""


async def _model_fill_step(page, step_name: str, payload: dict, dry_run: bool = False) -> None:
    """
    Read the raw HTML of the current form step, send it to Gemini Flash,
    and ask it to identify ONLY mandatory (*) fields and return CSS selectors + values.
    Execute those fill instructions via Playwright.
    Using HTML (not a screenshot) gives the model exact IDs/names/labels to work with.
    """
    fp = payload["form_payload"]
    street_address, apt_number = _parse_address(fp["address"])
    available_data = {
        "street_address":        street_address,
        "apt_number":            apt_number,
        "borough":               fp.get("borough", ""),
        "complaint_type":        fp.get("complaint_type", ""),
        "descriptor":            fp.get("descriptor", ""),
        "description":           fp.get("description", ""),
        "first_name":            payload.get("first_name", ""),
        "last_name":             payload.get("last_name", ""),
        "email":                 payload.get("email", ""),
        "phone":                 payload.get("phone", ""),
        "number_of_children":    "0",
        "children_in_household": "No",
        # For cascading dropdowns — pick the most relevant available option
        "_hint": (
            "For 'Additional Details' and 'Location Detail' dropdowns: "
            "pick whichever available option best matches the complaint type/descriptor. "
            "If unsure, pick the first non-empty option. "
            "For any field asking about children, minors, or kids in the household: use 0 or No."
        ),
    }
    logger.info(f"[Model:{step_name}] Available data: {json.dumps(available_data)}")

    # Extract visible form fields as compact JSON — avoids sending 1MB+ of HTML
    fields_json = await page.evaluate("""
        () => {
            const fields = [];
            const seenRadioNames = new Set();

            const els = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
            els.forEach(el => {
                if (!el.offsetParent) return;  // skip hidden elements

                // Group radio buttons by name — emit one entry per group
                if (el.type === 'radio') {
                    if (seenRadioNames.has(el.name)) return;
                    seenRadioNames.add(el.name);

                    // Find all options for this radio group
                    const radios = Array.from(document.querySelectorAll('input[type="radio"][name="' + el.name + '"]'));
                    const options = radios.map(r => {
                        let lbl = '';
                        if (r.id) {
                            const l = document.querySelector('label[for="' + r.id + '"]');
                            if (l) lbl = l.innerText.trim();
                        }
                        return lbl || r.value;
                    });

                    // Find group label from closest container
                    let groupLabel = '';
                    const container = el.closest('.form-group, fieldset, .field-container, td, li, div');
                    if (container) {
                        const lbl = container.querySelector('label:not([for])') ||
                                    container.querySelector('legend') ||
                                    container.querySelector('label');
                        if (lbl) groupLabel = lbl.innerText.trim();
                    }

                    fields.push({
                        tag: 'INPUT', type: 'radio',
                        name: el.name, id: el.id || '',
                        label: groupLabel,
                        options: options,
                        mandatory: groupLabel.includes('*'),
                    });
                    return;
                }

                // Find label text for non-radio fields
                let labelText = '';
                if (el.id) {
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) labelText = lbl.innerText.trim();
                }
                if (!labelText) {
                    const parent = el.closest('.form-group, .field-container, td, li');
                    if (parent) {
                        const lbl = parent.querySelector('label');
                        if (lbl) labelText = lbl.innerText.trim();
                    }
                }
                const field = {
                    tag:         el.tagName,
                    type:        el.type || '',
                    id:          el.id || '',
                    name:        el.name || '',
                    value:       el.value || '',
                    label:       labelText,
                    placeholder: el.placeholder || '',
                    mandatory:   labelText.includes('*'),
                };
                if (el.tagName === 'SELECT') {
                    field.options = Array.from(el.options).map(o => o.text.trim()).filter(t => t);
                }
                fields.push(field);
            });
            return JSON.stringify(fields);
        }
    """)
    parsed_fields = json.loads(fields_json)
    logger.info(f"[Model:{step_name}] Extracted {len(parsed_fields)} visible fields")
    logger.info(f"[Model:{step_name}] Fields: {json.dumps(parsed_fields, indent=2)}")

    prompt = f"""You are a form-filling assistant for an NYC 311 complaint form.

Below is a JSON list of ALL visible form fields on the current step called "{step_name}".
Each field has: tag, type, id, name, current value, label, placeholder, and (for selects/radios) available options.

Your job:
1. For each visible field that is empty, check if the available data has a matching value.
2. Match fields by their label or placeholder to the best key in the available data.
3. For SELECT fields: pick the option text that best matches the available data value.
4. For RADIO fields: pick the option label from the options list that best matches the data. Use "No" for any question about children, minors, or kids unless data says otherwise.
5. Skip fields that already have a value, or where nothing in the available data is relevant.
6. Do NOT fill fields with id/name containing "SelectAddressWhere" or "search-terms".
7. Return ONLY a JSON array. No explanation, no markdown, no code fences.

Available data:
{json.dumps(available_data, indent=2)}

Visible form fields:
{fields_json}

Return format (use name attribute as selector for radio fields, #id for others):
[
  {{"label": "Complaint Type",              "selector": "#ctype_id",        "value": "UNSANITARY CONDITION", "type": "select"}},
  {{"label": "Description",                 "selector": "#n311_desc",        "value": "Tenant reports...",   "type": "fill"}},
  {{"label": "Does a child under six...",   "selector": "[name='childname']", "value": "No",                 "type": "radio"}}
]

If no fields match the available data, return: []
"""

    # gemini-1.5-flash-001: 1500 RPD free tier (vs 20 for gemini-3-flash)
    response = None
    for attempt in range(3):
        try:
            response = form_client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=prompt,
            )
            break
        except Exception as e:
            if attempt < 2 and ("503" in str(e) or "429" in str(e)):
                wait = 10 * (attempt + 1)
                logger.warning(f"[Model:{step_name}] Error on attempt {attempt+1}, retrying in {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                logger.error(f"[Model:{step_name}] Gemini error: {e} — skipping fill")
                return

    raw = response.text.strip()
    # Strip markdown code fences if model wrapped the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()
    logger.info(f"[Model:{step_name}] Raw response: {raw}")

    try:
        instructions = json.loads(raw)
    except Exception:
        logger.warning(f"[Model:{step_name}] Could not parse JSON — skipping model fill")
        return

    logger.info(f"[Model:{step_name}] Parsed {len(instructions)} instruction(s): {json.dumps(instructions, indent=2)}")

    if dry_run:
        logger.info(f"[Model:{step_name}] DRY RUN — skipping actual fills")
        return

    for instr in instructions:
        if instr.get("skip") or not instr.get("value"):
            continue
        label     = instr.get("label", "")
        value     = str(instr["value"])
        selector  = instr.get("selector", "")
        fill_type = instr.get("type", "fill")   # "fill" or "select"
        filled    = False

        if selector:
            try:
                if fill_type == "radio":
                    # Find the radio input whose associated label text matches value
                    # selector from model is like [name='fieldname'] or #someid
                    radio_inputs = await page.locator(f"input[type='radio']{selector}").all()
                    clicked = False
                    for r in radio_inputs:
                        try:
                            r_id = await r.get_attribute("id")
                            lbl = page.locator(f"label[for='{r_id}']") if r_id else None
                            lbl_text = (await lbl.inner_text()).strip() if lbl and await lbl.count() > 0 else ""
                            if value.lower() in lbl_text.lower():
                                await r.click()
                                logger.info(f"[Model:{step_name}] Radio clicked {r_id!r} = {value!r}")
                                clicked = True
                                filled = True
                                break
                        except Exception:
                            pass
                    if not clicked:
                        # fallback: click the label with matching text
                        lbl = page.locator(f"label:has-text('{value}')").first
                        if await lbl.is_visible(timeout=1000):
                            await lbl.click()
                            logger.info(f"[Model:{step_name}] Radio label clicked = {value!r}")
                            filled = True
                else:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=1500):
                        if fill_type == "select":
                            await el.select_option(label=value)
                            logger.info(f"[Model:{step_name}] Selected {selector!r} = {value!r}")
                        else:
                            await el.fill(value)
                            logger.info(f"[Model:{step_name}] Filled {selector!r} = {value!r}")
                        filled = True
            except Exception:
                # If select_option by label fails, try by value
                if fill_type == "select":
                    try:
                        el = page.locator(selector).first
                        await el.select_option(value=value)
                        logger.info(f"[Model:{step_name}] Selected (by value) {selector!r} = {value!r}")
                        filled = True
                    except Exception:
                        pass

        # Fall back to label text search
        if not filled and label:
            try:
                el = page.get_by_label(label, exact=False)
                if await el.is_visible(timeout=1500):
                    if fill_type == "select":
                        await el.select_option(label=value)
                    else:
                        await el.fill(value)
                    logger.info(f"[Model:{step_name}] Filled (by label) {label!r} = {value!r}")
                    filled = True
            except Exception:
                pass

        if not filled:
            logger.warning(f"[Model:{step_name}] Could not fill: {label!r} (selector={selector!r})")


async def open_311_browser(payload: dict) -> dict:
    """
    Phase 1 — Playwright: navigate to 311, dismiss banner, trigger form via JS.
    Phase 2+ — Gemini Flash vision: screenshot each step, fill only mandatory (*) fields.
    Stops at Review — tenant clicks Submit themselves. Never auto-submits.
    """
    from playwright.async_api import async_playwright

    fp                       = payload["form_payload"]
    street_address, apt_number = _parse_address(fp["address"])
    address                  = street_address   # only the street goes into the address popup

    logger.info(f"[Browser] Opening 311 for {address} (apt: {apt_number!r})")

    async with async_playwright() as p:
        # No slow_mo during navigation — only add it after form opens
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page    = await context.new_page()

        # ── PLAYWRIGHT PHASE: open the form ───────────────────────────────────
        logger.info("[Browser] Navigating to 311 article page...")
        await page.goto(
            "https://portal.311.nyc.gov/article/?kanumber=KA-01074",
            wait_until="domcontentloaded",   # faster than networkidle
        )

        # Dismiss cookie banner immediately — don't wait for full page load
        for btn_text in ["Close", "Accept", "Accept All", "I Agree", "OK"]:
            try:
                btn = page.get_by_role("button", name=btn_text, exact=False)
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    logger.info(f"[Browser] Dismissed banner: '{btn_text}'")
                    break
            except Exception:
                pass

        # Trigger form via JS — same-page redirect, no popup
        logger.info("[Browser] Triggering createServiceRequest...")
        await page.evaluate("""
            createServiceRequest(
                'af973791-d174-e811-a83a-000d3a33bdbd',
                'fb2c44e2-4590-e811-a95f-000d3a1c53e4',
                '22b8b85e-4817-f111-8341-000d3a4f630d',
                'be973791-d174-e811-a83a-000d3a33bdbd',
                'HPD',
                '3eb8b85e-4817-f111-8341-000d3a4f630d'
            )
        """)

        await page.wait_for_url("**/sr-step/**", timeout=12000)
        logger.info(f"[Browser] Form opened: {page.url}")

        # Wait for the form to fully render before interacting
        await page.wait_for_load_state("domcontentloaded")
        page.set_default_timeout(12000)
        await asyncio.sleep(2)

        # ── STEP 1: Address — hardcoded popup flow ────────────────────────────
        # button#SelectAddressWhere opens an address picker popup (not a typeahead).
        # Flow: click button → popup appears → type in popup input → pick suggestion
        #       → confirm with "Select Address" → popup closes → fill Apartment # → Next

        # Dismiss any survey/feedback overlay (Qualtrics QSIWebResponsive) that may block clicks
        try:
            await page.evaluate("document.querySelectorAll('.QSIWebResponsive').forEach(el => el.remove())")
            logger.info("[Browser] Qualtrics survey overlay removed")
        except Exception:
            pass

        logger.info("[Browser] Step 1 — clicking address picker button to open popup")
        await page.locator("button#SelectAddressWhere").click(force=True)
        await asyncio.sleep(1.5)   # give the popup time to render

        # The popup is a modal/overlay — find its search input
        # Try common modal containers first, fall back to any new visible text input
        popup_input = None
        for sel in [
            "[role='dialog'] input[type='text']",
            "[role='dialog'] input:not([type='hidden'])",
            ".modal.in input[type='text']",
            ".modal-body input[type='text']",
            ".popup input[type='text']",
            "dialog input[type='text']",
            # Last resort: any visible text input that appeared (popup added to DOM)
            "input[type='text']:visible",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    popup_input = el
                    logger.info(f"[Browser] Popup input found via: {sel!r}")
                    break
            except Exception:
                pass

        if popup_input is None:
            raise RuntimeError("Could not find address input inside the popup")

        # Fill the full address string and press Enter — this triggers the geocoder
        await popup_input.click()
        await popup_input.fill(address)
        await asyncio.sleep(1)
        await popup_input.press("Enter")
        logger.info("[Browser] Address entered and Enter pressed")

        # Immediately click "Select Address" button — no extra sleep
        await page.evaluate("document.querySelector('#SelectAddressMap')?.scrollIntoView()")
        confirm_btn = page.locator(
            "input#SelectAddressMap, "
            "button:has-text('Select Address'), "
            "input[value='Select Address']"
        ).first

        modal_closed = False

        # Poll up to 15s for the button to enable (map geocoding), then force-click
        for _ in range(15):
            try:
                if await confirm_btn.is_enabled():
                    await confirm_btn.click()
                    logger.info("[Browser] 'Select Address' button clicked (enabled)")
                    modal_closed = True
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        if not modal_closed:
            try:
                await confirm_btn.click(force=True)
                logger.info("[Browser] 'Select Address' button force-clicked (was disabled)")
                modal_closed = True
            except Exception as e:
                logger.warning(f"[Browser] Force-click on confirm button failed: {e}")

        # Wait for modal to close
        if modal_closed:
            try:
                await page.locator("[role='dialog'].in, .modal.in").wait_for(state="hidden", timeout=5000)
                logger.info("[Browser] Address picker modal closed")
            except Exception:
                await page.evaluate("""
                    document.querySelectorAll('.modal.in').forEach(m => m.remove());
                    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                    document.body.classList.remove('modal-open');
                """)
                logger.warning("[Browser] Modal force-removed from DOM after confirm click")
        else:
            try:
                close_btn = page.locator(
                    "[role='dialog'].in .modal-header button.close, "
                    "[role='dialog'].in button[data-dismiss='modal']"
                ).first
                await close_btn.click(timeout=3000)
                await page.locator("[role='dialog'].in").wait_for(state="hidden", timeout=5000)
                logger.info("[Browser] Modal closed via X button")
            except Exception:
                await page.evaluate("""
                    document.querySelectorAll('.modal.in').forEach(m => m.remove());
                    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                    document.body.classList.remove('modal-open');
                """)
                logger.warning("[Browser] Modal force-removed from DOM")

        await asyncio.sleep(0.5)
        logger.info("[Browser] Address step complete")

        # Hardcode Apartment # using exact field ID confirmed from the 311 form DOM
        if apt_number:
            try:
                apt_field = page.locator("input#n311_apartmentnumber")
                await apt_field.wait_for(state="visible", timeout=4000)
                await apt_field.fill(apt_number)
                logger.info(f"[Browser] Apartment # filled: {apt_number!r}")
            except Exception as e:
                logger.warning(f"[Browser] Could not fill #n311_apartmentnumber: {e}")

        await page.locator("#NextButton").click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(4)   # complaint step dropdowns load asynchronously — wait for them
        logger.info("[Browser] Step 1 complete — now on complaint step")

        # ── STEP 2: Complaint fields — 4 passes for cascading dropdowns ─────────
        # Pass 1: Problem
        # Pass 2: Problem Detail (unlocked after Problem)
        # Pass 3: Additional Details (unlocked after Problem Detail)
        # Pass 4: Location Detail (unlocked after Additional Details)
        logger.info("[Browser] Step 2 — model filling complaint fields (4-pass cascade)")
        for pass_num in range(1, 5):
            logger.info(f"[Browser] Step 2 pass {pass_num}")
            await _model_fill_step(page, f"Step 2 pass {pass_num}", payload)
            await asyncio.sleep(2)   # wait for next dropdown to populate

        await page.locator("#NextButton").click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        logger.info("[Browser] Step 2 complete — now on contact step")

        # ── STEP 3 (Who): Contact info — first name, last name, email, phone ──
        logger.info("[Browser] Step 3 — model filling contact fields")
        await _model_fill_step(page, "Step 3 - Who", payload)

        await page.locator("#NextButton").click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        logger.info("[Browser] Step 3 complete")

        # ── STEP 4 (buffer): fill any remaining fields before Review ──────────
        # Some complaint types have an extra step (description, children, etc.)
        logger.info("[Browser] Step 4 — model filling any remaining fields")
        await _model_fill_step(page, "Step 4 - Extra", payload)

        # Only click Next if there's a NextButton (Review step has Submit, not Next)
        next_btn = page.locator("#NextButton")
        if await next_btn.is_visible(timeout=2000):
            await next_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            logger.info("[Browser] Step 4 complete — now on review step")

        # ── STEP 5: Review — stop here, tenant submits ────────────────────────
        logger.info("[Browser] Review step: waiting for tenant to submit")

        result = {
            "status":  "form_ready",
            "url":     page.url,
            "message": "Form pre-filled. Review and click Submit to file your complaint.",
        }

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
        submission = await open_311_browser(payload)
        result["status"] = "form_opened"
        result["submission"] = submission

    return result
