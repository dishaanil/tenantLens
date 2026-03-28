"""
agent.py
Perception Agent — A2A entry point
FastAPI server on port 8001.
Eng 3's ADK orchestrator calls POST /run to trigger the perception pipeline.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

from camera_feed import get_frame_base64
from gemini_vision import analyze_frame
from violation_parser import parse

load_dotenv()

app = FastAPI(title="TenantLens Perception Agent", version="1.0.0")


# ── Request / Response ─────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    address: str
    borough: str
    preferred_language: str = "en"
    frame_base64: Optional[str] = None # if None, agent captures from device camera


class RunResponse(BaseModel):
    violation_type: str
    confidence: str
    description: str
    address: str


# ── Agent Card ─────────────────────────────────────────────────────────────────
# Eng 3 fetches this on orchestrator startup for A2A discovery

AGENT_CARD = {
    "name": "perception_agent",
    "version": "1.0.0",
    "description": "Captures a camera frame and identifies housing violations using Gemini Flash.",
    "endpoint": "http://localhost:8001/run",
    "skill_file": "identify_violation.md",
    "input": {
        "address": "str",
        "frame_base64": "str (optional)",
    },
    "output": {
        "violation_type": "mold | water_damage | pest_damage | pest_infestation | broken_fixture | structural_damage | heating_issue | none",
        "confidence": "high | medium | low",
        "description": "str",
        "address": "str",
    },
    "next_agent": "http://localhost:8002/run",
}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": "perception_agent"}


@app.get("/.well-known/agent-card")
def agent_card():
    """A2A discovery — Eng 3's orchestrator calls this on startup."""
    return AGENT_CARD


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    """
    Main A2A pipeline:
    1. Get frame (from request payload or device camera)
    2. Send to Gemini Flash
    3. Parse response
    4. Return ViolationType payload to orchestrator
    """
    try:
        frame_b64 = req.frame_base64 if req.frame_base64 else get_frame_base64()
        raw_text = analyze_frame(frame_b64)
        violation = parse(raw_text)
        return RunResponse(**violation.to_a2a_payload(
    req.address, 
    req.borough, 
    req.preferred_language
))

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Perception pipeline error: {e}")


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    print(f"Perception Agent starting on :{port}")
    uvicorn.run("agent:app", host="0.0.0.0", port=port, reload=True)
