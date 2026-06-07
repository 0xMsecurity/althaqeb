"""Scan API routes."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from althaqeb.core.engine import Engine
from althaqeb.core.session import SessionManager

router = APIRouter()
_session_mgr = SessionManager()


class ScanRequest(BaseModel):
    target_url: str
    module: str = "all"
    api_key: Optional[str] = None


class ScanStatusResponse(BaseModel):
    session_id: str
    status: str
    target_url: str
    module: str
    findings_count: int


@router.post("/", response_model=ScanStatusResponse)
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Start a new scan and return the session ID immediately."""
    from althaqeb.core.session import ScanSession
    session = ScanSession(target_url=req.target_url, module=req.module)
    _session_mgr.save(session)

    background_tasks.add_task(
        _run_scan_bg, session.id, req.target_url, req.module, req.api_key
    )

    return ScanStatusResponse(
        session_id=session.id,
        status="running",
        target_url=req.target_url,
        module=req.module,
        findings_count=0,
    )


@router.get("/")
async def list_scans():
    """List recent scan sessions."""
    return _session_mgr.list_sessions()


@router.get("/{session_id}")
async def get_scan(session_id: str):
    """Get a specific scan session by ID."""
    session = _session_mgr.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.delete("/{session_id}")
async def delete_scan(session_id: str):
    """Delete a scan session."""
    from pathlib import Path
    from althaqeb.core.session import SESSIONS_DIR
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return {"deleted": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


def _run_scan_bg(session_id: str, target_url: str, module: str, api_key: Optional[str]) -> None:
    engine = Engine()
    session = engine.run_scan(target_url, module=module, api_key=api_key)
    session.id = session_id
    _session_mgr.save(session)
