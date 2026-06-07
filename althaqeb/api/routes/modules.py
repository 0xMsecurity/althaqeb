"""Module info API routes."""

from fastapi import APIRouter

router = APIRouter()

MODULES = [
    {"name": "injection",   "layer": "ATTACK",   "techniques": 30, "status": "active"},
    {"name": "extraction",  "layer": "ATTACK",   "techniques": 20, "status": "active"},
    {"name": "jailbreak",   "layer": "ATTACK",   "techniques": 15, "status": "active"},
    {"name": "agent",       "layer": "ATTACK",   "techniques": 10, "status": "partial"},
    {"name": "model-audit", "layer": "TRUST",    "techniques": 8,  "status": "partial"},
    {"name": "rag-monitor", "layer": "DEFEND",   "techniques": 5,  "status": "planned"},
    {"name": "ttp-db",      "layer": "INTEL",    "techniques": 84, "status": "partial"},
]


@router.get("/")
async def list_modules():
    return MODULES
