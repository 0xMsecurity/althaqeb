"""FastAPI server — REST API + WebSocket for the Althaqeb GUI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from althaqeb import __version__
from althaqeb.api.routes import scans, targets, reports, modules
from althaqeb.api.websocket import router as ws_router

GUI_DIR = Path(__file__).parent.parent / "gui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="الثاقب — Althaqeb API",
        description="AI Security Lifecycle Framework REST API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routers
    app.include_router(scans.router,   prefix="/api/v1/scans",   tags=["scans"])
    app.include_router(targets.router, prefix="/api/v1/targets", tags=["targets"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])

    # WebSocket
    app.include_router(ws_router)

    # Serve static GUI files
    if GUI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(GUI_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_gui():
            return FileResponse(str(GUI_DIR / "index.html"))

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "version": __version__, "framework": "الثاقب — Althaqeb"}

    return app
