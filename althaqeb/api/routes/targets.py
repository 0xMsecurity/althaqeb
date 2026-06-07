"""Target profiling API routes."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from althaqeb.core.engine import Engine

router = APIRouter()


class ProfileRequest(BaseModel):
    url: str
    api_key: Optional[str] = None


@router.post("/profile")
async def profile_target(req: ProfileRequest):
    """Profile and fingerprint a target AI system."""
    engine = Engine()
    return engine.profile_target(req.url, api_key=req.api_key)
