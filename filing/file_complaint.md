# file_complaint — Filing Agent Skill

## What this agent does
Can perform browser-based navigation including address verification and dynamic form mapping. Uses Playwright to simulate human interactions (typing, clicking, and selecting) to bypass basic bot-detection while maintaining user agency.
Receives the structured Agent 2 payload, narrates the tenant's legal rights as
spoken audio via Gemini Pro, presents a pre-filled 311 complaint form for
tenant review, and opens the NYC 311 housing complaint form in a browser with
all fields pre-filled. The tenant confirms and submits.

## Input
Full JSON payload from Agent 2. Required fields:
- `address` — building address string
- `violation_type` — string (e.g. "mold", "pest infestation")
- `tenant_rights` — array of legal rights strings (must not be modified)
- `form_payload` — object with: complaint_type, descriptor, address, borough, description
- `preferred_language` — ISO 639-1 code (e.g. "en", "es", "zh")
- `landlord_in_breach` — boolean
- `open_violations`, `class_c_open`, `class_b_open`, `oldest_open_days` — integers

## Output
```json
{
  "status": "awaiting_confirmation" | "form_opened",
  "audio_b64": "<base64 PCM audio of rights narration>",
  "form_review": {
    "fields": [{ "label": "...", "value": "..." }],
    "context": { "violation_type": "...", "open_violations": 9, ... },
    "confirmation_prompt": "Does this look correct? Confirm to submit to NYC 311."
  },
  "submission": { "status": "form_ready", "url": "...", "prefilled_data": { ... } }
}
```

## What this agent must never do
- Never submit the 311 complaint without explicit tenant confirmation
- Never modify the legal language in the `tenant_rights` array
- Never expose raw HPD API responses or internal error details to the tenant
- Never proceed to the browser agent step unless `tenant_confirmed=True` is passed
