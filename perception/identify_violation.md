# identify_violation

## What this agent does
Captures one camera frame from a tenant's phone and identifies housing maintenance violations using Gemini Flash vision.

## Input
```json
{
  "address": "string — tenant building address (from UI)",
  "frame_base64": "string (optional) — base64 JPEG. Omit to capture from device camera."
}
```

## Detection categories
`mold` · `water_damage` · `pest_damage` · `pest_infestation` · `broken_fixture` · `structural_damage` · `heating_issue` · `none`

## Output — frozen contract (do not rename fields)
```json
{
  "violation_type": "mold",
  "confidence": "high",
  "description": "Black mold on bathroom ceiling, approximately 30% coverage.",
  "address": "243 94th St, Brooklyn"
}
```

## Model
`gemini-3.1-flash-lite-preview` — chosen for low latency on real-time camera input.

## Endpoint
`POST http://localhost:8001/run`
Agent Card: `GET http://localhost:8001/.well-known/agent-card`
