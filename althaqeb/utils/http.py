"""HTTP client wrapper for Althaqeb scan operations."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class AIClient:
    """Thin wrapper around httpx for talking to AI API endpoints."""

    DEFAULT_TIMEOUT = 30.0

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.Client(headers=headers, timeout=timeout)

    def chat(self, messages: list[dict], model: str = "gpt-4", **kwargs: Any) -> dict:
        """Send a chat completion request (OpenAI-compatible API)."""
        payload = {"model": model, "messages": messages, **kwargs}
        response = self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def complete(self, prompt: str, model: str = "gpt-4", **kwargs: Any) -> str:
        """Send a single-prompt chat request and return the text response."""
        resp = self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            **kwargs,
        )
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return str(resp)

    def probe(self) -> dict:
        """Probe the target for basic connectivity and response info."""
        try:
            resp = self._client.get(f"{self.base_url}/v1/models", timeout=5.0)
            return {
                "reachable": True,
                "status_code": resp.status_code,
                "has_models_endpoint": resp.status_code == 200,
            }
        except httpx.RequestError as e:
            return {"reachable": False, "error": str(e)}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AIClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
