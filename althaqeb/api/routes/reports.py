"""Report generation API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from althaqeb.core.session import SessionManager
from althaqeb.reports.generator import ReportGenerator

router = APIRouter()
_session_mgr = SessionManager()
_report_gen = ReportGenerator()


@router.get("/{session_id}/html", response_class=HTMLResponse)
async def get_html_report(session_id: str):
    """Generate and return an HTML report for a session."""
    session = _session_mgr.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    html = _report_gen.generate_html(session)
    return HTMLResponse(content=html)


@router.get("/{session_id}/json")
async def get_json_report(session_id: str):
    """Return the raw JSON report for a session."""
    session = _session_mgr.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()
