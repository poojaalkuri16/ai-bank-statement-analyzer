"""
api_server.py
=============
FastAPI backend for the Finance AI Agent chat frontend.

Start with:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Endpoints
---------
GET  /api/health         — liveness check
POST /api/upload         — accept a PDF, process it, return session_id + summary
POST /api/chat           — answer one question for an active session

Sessions are stored in-memory (dict keyed by uuid4 string).
They exist only for the lifetime of this process — no database needed
for this single-user local demo.

Performance note
----------------
/api/upload calls FinanceAgent().process_statement() which internally
initialises Ollama-backed sub-agents.  Cold-start latency (first call
after Ollama model load) can reach ~235 s; warm calls are ~21 s.
The frontend must display a persistent loading state and must NOT use
a short HTTP client timeout for this endpoint.
"""

from __future__ import annotations

import sys
# Force stdout and stderr to use UTF-8 encoding on Windows to prevent UnicodeEncodeError
# when writing/printing characters like checkmarks (✓) to the console.
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Finance Agent ────────────────────────────────────────────────────────────
# Import from the existing src package; this file lives next to run.py so the
# relative imports work when uvicorn is started from the Finance/ directory.
from src.agents.finance.finance_agent import FinanceAgent
from src.context.session_context import SessionContextManager

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Finance AI Agent API", version="1.0.0")

# Permissive CORS — local demo only, no authentication required
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ───────────────────────────────────────────────────
# { session_id: { "agent": FinanceAgent, "context": SessionContextManager } }
_sessions: dict[str, dict[str, Any]] = {}


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str


class UploadSummary(BaseModel):
    session_id: str
    summary: dict[str, Any]


class HealthResponse(BaseModel):
    status: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Trivial liveness check."""
    return HealthResponse(status="ok")


@app.post("/api/upload", response_model=UploadSummary)
async def upload_statement(file: UploadFile = File(...)) -> UploadSummary:
    """
    Accept a PDF bank statement, process it with FinanceAgent, and return
    a session_id along with a brief summary extracted from the report.

    This endpoint can be SLOW on first call (~235 s cold start if the
    Ollama model hasn't been loaded yet).  The frontend must show a
    persistent loading indicator and not time out early.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    # Save uploaded bytes to a temporary file so FinanceAgent can read it
    try:
        contents = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {exc}",
        )

    tmp_path: Path | None = None
    try:
        # Use a named temp file with .pdf suffix so downstream parsers
        # can identify the format by extension if needed
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as tmp:
            tmp.write(contents)
            tmp_path = Path(tmp.name)

        agent = FinanceAgent()

        try:
            context: SessionContextManager = agent.process_statement(tmp_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Failed to process the PDF. "
                    f"The file may be corrupt, password-protected, or in an "
                    f"unsupported format.\n\nDetail: {exc}"
                ),
            )

        report = agent.get_report(context)
        if report is None:
            raise HTTPException(
                status_code=500,
                detail="Processing completed but no report was generated.",
            )

        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            "agent":   agent,
            "context": context,
        }

        summary: dict[str, Any] = {
            "transaction_count":    report.transaction_count,
            "statement_start_date": (
                report.statement_start_date.isoformat()
                if report.statement_start_date else None
            ),
            "statement_end_date": (
                report.statement_end_date.isoformat()
                if report.statement_end_date else None
            ),
            "extraction_confidence": round(report.extraction_confidence * 100, 1),
            "bank_name":             report.bank_name or "Unknown",
            "statement_name":        report.statement_name,
        }

        return UploadSummary(session_id=session_id, summary=summary)

    finally:
        # Clean up the temp file whether or not processing succeeded
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass  # best-effort cleanup


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Answer one natural-language question about a previously uploaded statement.

    The SessionContextManager stored for this session accumulates conversation
    context server-side, enabling follow-up questions like:
      "Show my largest debit" → "Who was it paid to?" → "When did it happen?"
    The frontend just needs to keep sending the same session_id.
    """
    session = _sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{request.session_id}' not found. "
                "Please upload a statement first."
            ),
        )

    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message must not be empty.",
        )

    agent:   FinanceAgent           = session["agent"]
    context: SessionContextManager  = session["context"]

    try:
        answer: str = agent.ask(
            context=context,
            question=request.message.strip(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate an answer: {exc}",
        )

    return ChatResponse(answer=answer)
