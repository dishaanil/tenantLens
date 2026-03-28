"""
TenantLens — ADK Orchestrator

A2A routing: Agent 1 (Perception) → Agent 2 (Data+Rights) → Agent 3 (Filing)
Exposes a FastAPI HTTP interface for the frontend and Cloud Run health checks.
"""

import os
import json
import logging
import asyncio
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from google import genai
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("orchestrator")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

app = FastAPI(title="TenantLens Orchestrator", version="1.0.0")

# ---------------------------------------------------------------------------
# Tool wrappers — each tool delegates to the real agent module
# ---------------------------------------------------------------------------

def identify_violation_tool(image_base64: str) -> dict:
    """
    Agent 1: Receives a base64-encoded camera frame.
    Returns: { "violation_type": "mold" | "pest infestation" | ... }
    """
    try:
        import sys
        sys.path.insert(0, "/app")
        from perception.agent import identify_violation
        result = identify_violation(image_base64)
        logger.info(f"[Agent1] Violation identified: {result}")
        return result
    except Exception as e:
        logger.error(f"[Agent1] Error: {e}")
        return {"error": str(e), "violation_type": None}


def lookup_hpd_tool(violation_type: str, address: str, borough: str, preferred_language: str = "en") -> dict:
    """
    Agent 2: Queries HPD Open Data and applies rights logic.
    address — street address only (e.g. "2386 VALENTINE AVENUE")
    borough — borough name (e.g. "Bronx", "Brooklyn", "Manhattan")
    Returns: full structured payload (see Agent 2 payload contract).
    """
    try:
        import sys
        sys.path.insert(0, "/app")
        from data.agent import run_agent
        result = run_agent(
            violation_type=violation_type,
            address=address,
            borough=borough,
            preferred_language=preferred_language,
        )
        logger.info(f"[Agent2] HPD lookup complete: {result.get('open_violations')} open violations, breach={result.get('landlord_in_breach')}")
        return result
    except Exception as e:
        logger.error(f"[Agent2] Error: {e}")
        return {"error": str(e)}


async def file_complaint_tool(payload: dict, tenant_confirmed: bool = False) -> dict:
    """
    Agent 3: Narrates rights, shows form review, submits on confirmation.
    Returns: audio + form review + optional submission result.
    """
    try:
        import sys
        sys.path.insert(0, "/app")
        from filing.agent import run as filing_run
        result = await filing_run(payload=payload, tenant_confirmed=tenant_confirmed)
        logger.info(f"[Agent3] Filing result status: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"[Agent3] Error: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# ADK Agent definitions
# ---------------------------------------------------------------------------

perception_agent = LlmAgent(
    name="perception_agent",
    model="gemini-2.0-flash-exp",
    description="Identifies housing violations from camera frames using Gemini Flash vision.",
    instruction=(
        "You are a housing violation detector. "
        "When given an image, identify the housing condition and return a violation_type string. "
        "Valid types: mold, pest infestation, water damage, broken heat, leaking pipes, "
        "broken fixtures, structural damage, inadequate lighting, peeling paint. "
        "Return only the violation_type string."
    ),
    tools=[FunctionTool(identify_violation_tool)],
)

data_agent = LlmAgent(
    name="data_agent",
    model="gemini-2.0-flash-exp",
    description="Queries NYC HPD Open Data and computes tenant rights and breach status.",
    instruction=(
        "You are a NYC housing data analyst. "
        "Given a violation_type and address, use the lookup_hpd tool to fetch HPD violation history "
        "and produce the full structured payload for the filing agent."
    ),
    tools=[FunctionTool(lookup_hpd_tool)],
)

filing_agent = LlmAgent(
    name="filing_agent",
    model="gemini-2.0-flash-exp",
    description="Narrates tenant rights as audio and submits 311 complaints on confirmation.",
    instruction=(
        "You are a tenant rights advocate. "
        "Use the file_complaint tool with the Agent 2 payload. "
        "Never submit without tenant_confirmed=True. "
        "Never modify tenant_rights language."
    ),
    tools=[FunctionTool(file_complaint_tool)],
)

pipeline = SequentialAgent(
    name="tenantlens_pipeline",
    sub_agents=[perception_agent, data_agent, filing_agent],
    description="Full TenantLens A2A pipeline: vision → HPD data → rights narration + 311 filing.",
)

session_service = InMemorySessionService()
runner = Runner(
    agent=pipeline,
    app_name="tenantlens",
    session_service=session_service,
)

# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------

class ViolationRequest(BaseModel):
    image_base64: str
    address: str          # street address only, e.g. "2386 VALENTINE AVENUE"
    borough: str          # e.g. "Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"
    preferred_language: str = "en"
    session_id: str = "default"


class ConfirmRequest(BaseModel):
    session_id: str
    payload: dict


@app.get("/health")
def health():
    return {"status": "ok", "service": "tenantlens-orchestrator"}


@app.post("/analyze")
async def analyze(req: ViolationRequest):
    """
    Full pipeline: camera frame + address → rights narration + pre-filled 311 form.
    Returns audio bytes (b64) and form review. Does NOT submit — tenant confirms separately.
    """
    logger.info(f"[Orchestrator] /analyze called for address: {req.address}")

    try:
        # Step 1: Identify violation
        violation_result = identify_violation_tool(req.image_base64)
        if "error" in violation_result:
            raise HTTPException(status_code=502, detail=f"Agent 1 error: {violation_result['error']}")

        violation_type = violation_result["violation_type"]
        logger.info(f"[A2A 1→2] violation_type={violation_type}")

        # Step 2: HPD lookup + rights logic
        hpd_payload = lookup_hpd_tool(
            violation_type=violation_type,
            address=req.address,
            borough=req.borough,
            preferred_language=req.preferred_language,
        )
        if "error" in hpd_payload:
            raise HTTPException(status_code=502, detail=f"Agent 2 error: {hpd_payload['error']}")
        logger.info(f"[A2A 2→3] payload built, breach={hpd_payload.get('landlord_in_breach')}")

        # Step 3: Filing agent — narrate rights + form review (no submit yet)
        filing_result = await file_complaint_tool(payload=hpd_payload, tenant_confirmed=False)
        if "error" in filing_result:
            raise HTTPException(status_code=502, detail=f"Agent 3 error: {filing_result['error']}")

        logger.info(f"[Orchestrator] Pipeline complete. Status: {filing_result.get('status')}")
        return JSONResponse(content=filing_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Orchestrator] Unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/confirm")
async def confirm_submission(req: ConfirmRequest):
    """
    Called when the tenant confirms the pre-filled form.
    Triggers the browser agent to open the 311 form with data pre-filled.
    """
    logger.info(f"[Orchestrator] /confirm called, session={req.session_id}")

    try:
        result = await file_complaint_tool(payload=req.payload, tenant_confirmed=True)
        if "error" in result:
            raise HTTPException(status_code=502, detail=f"Filing error: {result['error']}")
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Orchestrator] Confirm error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator.main:app", host="0.0.0.0", port=8080, reload=True)
