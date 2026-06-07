"""Base class for all attack modules."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from althaqeb.core.results import Finding
from althaqeb.utils.logger import get_logger
from althaqeb.utils.scoring import quick_score

logger = get_logger(__name__)

PAYLOADS_DIR = Path(__file__).parent.parent.parent / "payloads"


class BaseAttackModule:
    """Common interface for all attack modules."""

    CATEGORY: str = "generic"
    LAYER: str = "ATTACK"

    def __init__(self, target_url: str, api_key: Optional[str] = None, verbose: bool = False):
        self.url = target_url.rstrip("/")
        self.api_key = api_key
        self.verbose = verbose
        self.findings: list[Finding] = []

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.Client(headers=headers, timeout=15.0)

    def run(self) -> list[Finding]:
        raise NotImplementedError

    def _send(self, messages: list[dict], model: str = "gpt-4", max_tokens: int = 200) -> Optional[str]:
        try:
            resp = self.client.post(
                f"{self.url}/v1/chat/completions",
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code == 429:
                logger.warning("[yellow]Rate limited — sleeping 3s[/yellow]")
                time.sleep(3)
            return None
        except Exception as e:
            if self.verbose:
                logger.debug(f"Send error: {e}")
            return None

    def _load_payloads(self, subpath: str) -> list[dict[str, Any]]:
        path = PAYLOADS_DIR / subpath
        if not path.exists():
            logger.warning(f"Payload file not found: {path}")
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _make_finding(
        self,
        technique: str,
        description: str,
        payload: str,
        response: str,
        confidence: float,
        atlas_id: Optional[str] = None,
        gcc_context: str = "general",
        autonomy: float = 0.3,
        blast_radius: float = 0.5,
    ) -> Finding:
        score_result = quick_score(
            autonomy=autonomy,
            blast_radius=blast_radius,
            gcc_context=gcc_context,
        )
        return Finding(
            technique=technique,
            category=self.CATEGORY,
            layer=self.LAYER,
            severity=score_result.severity,
            aivss_score=score_result.final_score,
            confidence=confidence,
            description=description,
            payload=payload,
            response=response,
            atlas_id=atlas_id,
            gcc_context=gcc_context,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "BaseAttackModule":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
