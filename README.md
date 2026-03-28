# tenantLens

<img width="586" height="534" alt="image" src="https://github.com/user-attachments/assets/8855342e-9997-489e-94d5-9f6df99e86d5" />



# TenantLens

**Know Your Rights. Point and Speak.**

TenantLens is a multimodal AI agent that empowers NYC renters to understand 
and enforce their housing rights — no legal knowledge required, no forms to 
fill, no English necessary.

Point your camera at a housing condition — mold, pest damage, broken heat, 
leaking pipes. TenantLens sees it, identifies the violation, cross-references 
your building's live HPD violation history from NYC Open Data, speaks your 
rights back to you in your language, and auto-generates and submits a 311 
complaint on your behalf.

## Team

- Karthik Nair — Data Agent + Rights Logic
- Pooja — Perception Agent
- Disha Anil — Filing Agent + ADK Orchestrator + Cloud Run Deployment
- Teja — Frontend + Demo + Pitch

## How It Works

1. Tenant points phone camera at housing problem
2. Gemini Flash identifies the violation type
3. HPD Open Data API queried for building violation history
4. Rights logic determines if landlord is in breach
5. Gemini Pro narrates tenant rights in preferred language
6. Browser agent auto-fills and submits NYC 311 complaint

## Tech Stack

- Google ADK (Agent Development Kit) — multi-agent orchestration
- Gemini 2.5 Flash — real-time vision perception
- Gemini 2.5 Flash — legal narration and complaint generation
- A2A (Agent to Agent) — inter-agent communication
- NYC HPD Open Data API — violation history
- NYC 311 API — complaint submission
- FastAPI — agent servers
- Google Cloud Run — deployment
- Python 3.11+

## Architecture

Three agents communicating via A2A, orchestrated by Google ADK:

- **Agent 1 (Perception)** — camera → Gemini Flash → violation type
- **Agent 2 (Data + Rights)** — HPD query → breach logic → rights array → 311 payload
- **Agent 3 (Filing)** — voice narration → form review → 311 submission

## Project Structure
```
tenantLens/
├── orchestrator/    # ADK orchestrator, A2A routing
├── perception/      # Agent 1 — Gemini Flash vision
├── data/            # Agent 2 — HPD API + rights logic
├── filing/          # Agent 3 — voice output + 311 filing
├── frontend/        # Mobile web UI
├── .env.example     # Environment variables template
└── requirements.txt
```

## Setup
```bash
git clone https://github.com/dishaanil/tenantLens.git
cd tenantLens
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your GEMINI_API_KEY and NYC_OPEN_DATA_TOKEN to .env
```

## Environment Variables
```
GEMINI_API_KEY=
NYC_OPEN_DATA_TOKEN=
VERTEX_PROJECT_ID=tenantlens
VERTEX_LOCATION=us-central1
```

## Deployment
```bash
gcloud run deploy tenantlens --source . --region us-central1
```

## Built For

NYC Build With AI Hackathon — Google GDG x Columbia Business School  
NYC Open Data Week 2026
