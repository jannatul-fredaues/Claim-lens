"""
FastAPI backend for the Evidence Review demo frontend.

Wraps the exact same adjudication logic used by the batch pipeline
(code/claim_processor.py from the hackathon submission) behind a single
HTTP endpoint that accepts uploaded images + a claim description and
returns the structured verdict as JSON.

Run:
    cd backend
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-...
    uvicorn app:app --reload --port 8000

The frontend (frontend/index.html) expects this running at
http://localhost:8000.
"""
import json
import os
import sys
import tempfile
import time
from typing import List

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Reuse the exact pipeline logic from the hackathon submission's code/ directory.
# Point this at wherever you put schema.py / prompts.py / claim_processor.py.
PIPELINE_CODE_DIR = os.environ.get(
    "PIPELINE_CODE_DIR", os.path.join(os.path.dirname(__file__), "..", "pipeline")
)
sys.path.insert(0, PIPELINE_CODE_DIR)

import schema  # noqa: E402
from prompts import SYSTEM_PROMPT, build_user_prompt  # noqa: E402

app = FastAPI(title="Evidence Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only -- lock this down for anything real
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def adjudicate(claim_object: str, user_claim: str, images: List[dict]) -> dict:
    """
    images: list of {"id": str, "media_type": str, "data_b64": str}
    Mirrors claim_processor.process_claim but takes in-memory uploads
    instead of dataset CSV rows.
    """
    if not images:
        return {
            "evidence_standard_met": False,
            "evidence_standard_met_reason": "No images were uploaded with this claim.",
            "risk_flags": "none",
            "issue_type": "unknown",
            "object_part": "unknown",
            "claim_status": "not_enough_information",
            "claim_status_justification": "No images were uploaded with this claim.",
            "supporting_image_ids": "none",
            "valid_image": False,
            "severity": "unknown",
        }

    client = get_client()
    if client is None:
        return {
            "evidence_standard_met": False,
            "evidence_standard_met_reason": "ANTHROPIC_API_KEY is not configured on the server.",
            "risk_flags": "none",
            "issue_type": "unknown",
            "object_part": "unknown",
            "claim_status": "not_enough_information",
            "claim_status_justification": "Server is not configured to run vision adjudication.",
            "supporting_image_ids": "none",
            "valid_image": False,
            "severity": "unknown",
        }

    content = []
    ids = []
    for im in images:
        content.append({"type": "text", "text": f"Image ID: {im['id']}"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": im["media_type"], "data": im["data_b64"]},
        })
        ids.append(im["id"])

    user_text = build_user_prompt(
        claim_object=claim_object,
        user_claim=user_claim,
        requirement=None,  # wire in evidence_requirements.csv lookup here if available
        history_text="unknown (no user_history provided in this demo)",
        image_ids_in_order=ids,
        missing_image_paths=[],
    )
    content.append({"type": "text", "text": user_text})

    resp = client.messages.create(
        model=os.environ.get("CLAIM_REVIEW_MODEL", "claude-sonnet-4-6"),
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    parsed = _extract_json(text)

    return {
        "evidence_standard_met": bool(parsed.get("evidence_standard_met", False)),
        "evidence_standard_met_reason": str(parsed.get("evidence_standard_met_reason", "")),
        "risk_flags": schema.sanitize_risk_flags(parsed.get("risk_flags", [])),
        "issue_type": schema.closest_issue_type(str(parsed.get("issue_type", "unknown"))),
        "object_part": schema.closest_object_part(claim_object, str(parsed.get("object_part", "unknown"))),
        "claim_status": schema.closest_claim_status(str(parsed.get("claim_status", "not_enough_information"))),
        "claim_status_justification": str(parsed.get("claim_status_justification", "")),
        "supporting_image_ids": ";".join(
            [s for s in parsed.get("supporting_image_ids", []) if s in ids]
        ) or "none",
        "valid_image": bool(parsed.get("valid_image", False)),
        "severity": schema.closest_severity(str(parsed.get("severity", "unknown"))),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "model_configured": get_client() is not None}


@app.get("/api/debug")
def debug_paths():
    """Hit this on the live deploy to see exactly what the server sees on disk."""
    frontend_dir = os.environ.get(
        "FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend")
    )
    frontend_dir_abs = os.path.abspath(frontend_dir)
    return {
        "cwd": os.getcwd(),
        "__file__": os.path.abspath(__file__),
        "frontend_dir_resolved": frontend_dir_abs,
        "frontend_dir_exists": os.path.isdir(frontend_dir_abs),
        "frontend_dir_contents": os.listdir(frontend_dir_abs) if os.path.isdir(frontend_dir_abs) else None,
        "repo_root_listing": os.listdir(os.path.join(os.path.dirname(__file__), "..")),
    }


@app.post("/api/claims")
async def submit_claim(
    claim_object: str = Form(...),
    user_claim: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    import base64

    images = []
    for f in files:
        raw = await f.read()
        img_id = os.path.splitext(f.filename or f"image_{len(images)+1}")[0]
        images.append({
            "id": img_id,
            "media_type": f.content_type or "image/jpeg",
            "data_b64": base64.standard_b64encode(raw).decode("utf-8"),
        })

    started = time.time()
    try:
        result = adjudicate(claim_object, user_claim, images)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})

    result["latency_seconds"] = round(time.time() - started, 2)
    result["claim_object"] = claim_object
    result["user_claim"] = user_claim
    result["image_ids"] = [im["id"] for im in images]
    return result


# ---------------------------------------------------------------------------
# Serve the frontend (frontend/index.html, styles.css, app.js) from this same
# FastAPI app so a single deploy (e.g. one Render web service) serves both
# the UI and the API -- no separate static host, no cross-origin requests.
# Must be mounted LAST, after all /api/* routes above.
# ---------------------------------------------------------------------------
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend")
)
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)
print(f"[startup] FRONTEND_DIR resolved to: {FRONTEND_DIR}", flush=True)
print(f"[startup] FRONTEND_DIR exists: {os.path.isdir(FRONTEND_DIR)}", flush=True)

if os.path.isdir(FRONTEND_DIR):
    print(f"[startup] mounting static frontend from {FRONTEND_DIR}", flush=True)
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    print(f"[startup] WARNING: frontend dir not found, '/' will 404. Check /api/debug.", flush=True)

    @app.get("/")
    def frontend_missing():
        return JSONResponse(
            status_code=500,
            content={
                "error": "Frontend directory not found on server.",
                "frontend_dir_expected": FRONTEND_DIR,
                "hint": "Visit /api/debug to inspect the deployed file layout.",
            },
        )
