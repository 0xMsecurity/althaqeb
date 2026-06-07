"""WebSocket endpoint for live scan streaming."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from althaqeb.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/scan/{session_id}")
async def scan_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint that streams live scan progress for a given session.

    Messages are JSON with structure:
    {
        "type": "progress" | "finding" | "complete" | "error",
        "data": {...}
    }
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id[:8]}")

    try:
        from althaqeb.core.session import SessionManager, SESSIONS_DIR
        sm = SessionManager()

        # Poll for session updates and stream to client
        last_finding_count = 0
        timeout = 300  # 5 minute max per scan
        start = time.time()

        while time.time() - start < timeout:
            session = sm.load(session_id)

            if session is None:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": f"Session {session_id} not found"}
                })
                break

            # Send new findings
            current_count = len(session.findings)
            if current_count > last_finding_count:
                for finding in session.findings[last_finding_count:]:
                    await websocket.send_json({
                        "type": "finding",
                        "data": finding
                    })
                last_finding_count = current_count

            # Send progress update
            await websocket.send_json({
                "type": "progress",
                "data": {
                    "session_id": session_id,
                    "status": session.status,
                    "findings_count": current_count,
                    "elapsed": round(time.time() - start, 1),
                }
            })

            if session.status in ("completed", "failed"):
                await websocket.send_json({
                    "type": "complete",
                    "data": session.stats
                })
                break

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id[:8]}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
