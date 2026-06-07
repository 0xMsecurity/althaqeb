"""Scan session management — create, persist, and load scan sessions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from althaqeb.core.results import Finding


SESSIONS_DIR = Path.home() / ".althaqeb" / "sessions"


@dataclass
class ScanSession:
    """Represents a single scan or attack run."""

    id:           str = field(default_factory=lambda: str(uuid.uuid4()))
    target_url:   str = ""
    module:       str = "all"
    started_at:   float = field(default_factory=time.time)
    finished_at:  Optional[float] = None
    status:       str = "running"      # running / completed / failed
    findings:     list[dict[str, Any]] = field(default_factory=list)
    profile:      dict[str, Any] = field(default_factory=dict)
    stats:        dict[str, Any] = field(default_factory=dict)

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding.to_dict())

    def complete(self) -> None:
        self.finished_at = time.time()
        self.status = "completed"
        self.stats = {
            "duration_sec": round(self.finished_at - self.started_at, 2),
            "total_findings": len(self.findings),
            "by_severity": self._count_by_severity(),
            "max_score": max((f.get("aivss_score", 0.0) for f in self.findings), default=0.0),
        }

    def _count_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            sev = f.get("severity", "INFO")
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          self.id,
            "target_url":  self.target_url,
            "module":      self.module,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
            "status":      self.status,
            "findings":    self.findings,
            "profile":     self.profile,
            "stats":       self.stats,
        }


class SessionManager:
    """Persists sessions to ~/.althaqeb/sessions/."""

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.dir = sessions_dir or SESSIONS_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: ScanSession) -> Path:
        path = self.dir / f"{session.id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, session_id: str) -> Optional[ScanSession]:
        path = self.dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        s = ScanSession(
            id=data["id"],
            target_url=data.get("target_url", ""),
            module=data.get("module", "all"),
            started_at=data.get("started_at", 0),
            finished_at=data.get("finished_at"),
            status=data.get("status", "completed"),
            findings=data.get("findings", []),
            profile=data.get("profile", {}),
            stats=data.get("stats", {}),
        )
        return s

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        sessions = []
        for p in sorted(self.dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sessions.append({
                    "id":         data["id"],
                    "target_url": data.get("target_url", ""),
                    "module":     data.get("module", "all"),
                    "status":     data.get("status", "unknown"),
                    "findings":   len(data.get("findings", [])),
                    "started_at": data.get("started_at", 0),
                })
            except Exception:
                continue
        return sessions
