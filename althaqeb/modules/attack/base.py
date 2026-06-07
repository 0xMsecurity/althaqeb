"""Base class for all attack modules."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from althaqeb.core.results import Finding
from althaqeb.core.discovery import DiscoveredEndpoint
from althaqeb.utils.logger import get_logger
from althaqeb.utils.scoring import quick_score

logger = get_logger(__name__)

PAYLOADS_DIR = Path(__file__).parent.parent.parent / "payloads"


class BaseAttackModule:
    """Common interface for all attack modules."""

    CATEGORY: str = "generic"
    LAYER: str = "ATTACK"

    def __init__(
        self,
        target_url: str,
        api_key: Optional[str] = None,
        verbose: bool = False,
        endpoint: Optional[DiscoveredEndpoint] = None,
    ):
        self.url = target_url.rstrip("/")
        self.api_key = api_key
        self.verbose = verbose
        self.endpoint = endpoint
        self.findings: list[Finding] = []

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; Althaqeb-Scanner/0.1; security-research)",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(headers=headers, timeout=20.0, follow_redirects=True)

    def run(self) -> list[Finding]:
        raise NotImplementedError

    def _send(self, messages: list[dict], model: str = "gpt-4", max_tokens: int = 300) -> Optional[str]:
        """Send a chat message using the appropriate format for this endpoint."""
        if self.endpoint:
            return self._send_to_endpoint(self.endpoint, messages, max_tokens)

        # Default: try OpenAI-compat on the base URL
        return self._send_openai(f"{self.url}/v1/chat/completions", messages, model, max_tokens)

    def _send_to_endpoint(
        self,
        endpoint: DiscoveredEndpoint,
        messages: list[dict],
        max_tokens: int = 300,
    ) -> Optional[str]:
        if endpoint.format in ("openai", "unknown"):
            result = self._send_openai(endpoint.url, messages, "gpt-4", max_tokens)
            if result:
                return result

        # Try custom JSON format if openai failed or it's a custom endpoint
        if endpoint.format in ("custom_json", "unknown"):
            result = self._send_custom_json(endpoint.url, messages, max_tokens)
            if result:
                return result

        return None

    def _send_openai(
        self,
        url: str,
        messages: list[dict],
        model: str = "gpt-4",
        max_tokens: int = 300,
    ) -> Optional[str]:
        try:
            resp = self.client.post(
                url,
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            if resp.status_code == 429:
                logger.warning("[yellow]Rate limited — sleeping 3s[/yellow]")
                time.sleep(3)
                return None
            if resp.status_code == 200:
                body = resp.json()
                # OpenAI format
                if "choices" in body:
                    return body["choices"][0]["message"]["content"]
                # Anthropic-style
                if "content" in body and isinstance(body["content"], list):
                    return body["content"][0].get("text", "")
                # Simple response field
                for key in ("response", "message", "text", "answer", "output", "result"):
                    if key in body:
                        val = body[key]
                        return str(val) if not isinstance(val, dict) else json.dumps(val)
                # Last resort — dump the whole body
                return json.dumps(body)[:500]
        except httpx.TimeoutException:
            if self.verbose:
                logger.debug(f"Timeout: {url}")
        except Exception as e:
            if self.verbose:
                logger.debug(f"Send error ({url}): {e}")
        return None

    def _send_custom_json(
        self,
        url: str,
        messages: list[dict],
        max_tokens: int = 300,
    ) -> Optional[str]:
        """Try various common JSON chat API formats."""
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        payloads_to_try = [
            # Many custom chatbots just take a "message" or "query"
            {"message": last_user_msg},
            {"query": last_user_msg},
            {"text": last_user_msg},
            {"input": last_user_msg},
            {"prompt": last_user_msg},
            {"content": last_user_msg},
            {"question": last_user_msg},
            # Some take messages array with different field names
            {"messages": [{"role": "user", "content": last_user_msg}]},
            {"chat_history": [], "message": last_user_msg},
        ]

        for payload in payloads_to_try:
            try:
                resp = self.client.post(url, json=payload, timeout=12.0)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        body = resp.json()
                        text = _extract_text_from_response(body)
                        if text and len(text) > 3:
                            return text
                    elif "text" in ct:
                        text = resp.text.strip()
                        if text:
                            return text
            except Exception:
                continue

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


def _extract_text_from_response(body: Any) -> Optional[str]:
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        for key in ("response", "message", "text", "answer", "output", "result",
                    "choices", "content", "data", "reply", "bot", "assistant"):
            val = body.get(key)
            if val is None:
                continue
            if isinstance(val, str) and val:
                return val
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    # OpenAI choices format
                    msg = first.get("message", {})
                    if isinstance(msg, dict):
                        return msg.get("content", "")
                    return first.get("text", "") or first.get("content", "")
    return None
