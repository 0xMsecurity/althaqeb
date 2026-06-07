"""
AI endpoint discovery — finds the actual AI interface on a target web property.
Handles: OpenAI-compat APIs, custom chat APIs, embedded widgets, form endpoints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from althaqeb.utils.logger import get_logger

logger = get_logger(__name__)

# Paths to probe for AI/chat endpoints
CANDIDATE_PATHS = [
    "/v1/chat/completions",
    "/api/chat",
    "/api/chat/completions",
    "/api/v1/chat",
    "/api/v1/messages",
    "/api/message",
    "/api/messages",
    "/api/query",
    "/api/completion",
    "/api/completions",
    "/chat/api",
    "/chatbot/api",
    "/api/chatbot",
    "/api/bot",
    "/bot/message",
    "/widget/chat",
    "/api/widget/message",
    "/api/assistant",
    "/api/ask",
    "/api/search",
    "/api/support/chat",
    "/live-chat/api",
    "/chat",
]

# Third-party chat widget fingerprints found in HTML/JS
THIRD_PARTY_WIDGETS = {
    "tidio":      r"tidio|tidiochat",
    "intercom":   r"intercom(?:app)?\.io",
    "crisp":      r"crisp\.chat",
    "drift":      r"drift\.com",
    "zendesk":    r"zendesk|zopim|ze\.to",
    "freshchat":  r"freshchat|freshdesk",
    "tawk":       r"tawk\.to",
    "hubspot":    r"hubspot|hs-scripts",
    "helpscout":  r"helpscout",
    "olark":      r"olark\.com",
    "livechat":   r"livechat(?:inc)?\.com",
    "botpress":   r"botpress",
    "rasa":       r"rasa(?:chat|bot)?",
    "openai":     r"openai\.com|/v1/chat",
    "anthropic":  r"anthropic\.com|claude",
    "azure_oai":  r"azure.*openai|openai.*azure|cognitiveservices\.azure",
    "cohere":     r"cohere\.ai|cohere\.com",
    "gemini":     r"generativelanguage\.googleapis",
}

# JSON body patterns that look like chat API requests (found in inline JS)
CHAT_API_PATTERNS = [
    r'"messages"\s*:\s*\[',
    r'fetch\s*\(\s*["\']([^"\']+)["\'].*messages',
    r'axios\s*\.\s*post\s*\(\s*["\']([^"\']+)["\'].*messages',
    r'"role"\s*:\s*"user"',
    r'chat\s*\.\s*completions',
    r'/chat/completions',
]


@dataclass
class DiscoveredEndpoint:
    url:            str
    method:         str = "POST"                    # HTTP method to use
    format:         str = "openai"                  # openai / custom_json / form / unknown
    content_type:   str = "application/json"
    auth_required:  bool = False
    widget_type:    Optional[str] = None            # e.g. "tidio", "intercom"
    notes:          str = ""
    confidence:     float = 0.0                     # 0.0–1.0
    probe_response: Optional[str] = None            # sample response from probing


@dataclass
class DiscoveryResult:
    target_url:         str
    reachable:          bool = False
    is_web_app:         bool = False
    found_endpoints:    list[DiscoveredEndpoint] = field(default_factory=list)
    detected_widgets:   list[str] = field(default_factory=list)
    page_title:         str = ""
    server_header:      str = ""
    tech_stack:         list[str] = field(default_factory=list)
    notes:              list[str] = field(default_factory=list)

    @property
    def best_endpoint(self) -> Optional[DiscoveredEndpoint]:
        if not self.found_endpoints:
            return None
        return max(self.found_endpoints, key=lambda e: e.confidence)


class AIEndpointDiscovery:
    """Discovers AI interfaces on a target web property."""

    def __init__(self, timeout: float = 10.0, api_key: Optional[str] = None):
        self.timeout = timeout
        self.api_key = api_key

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Althaqeb-Scanner/0.1; security-research)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(headers=headers, timeout=timeout, follow_redirects=True)

    def discover(self, url: str) -> DiscoveryResult:
        result = DiscoveryResult(target_url=url)
        base = _base_url(url)

        # 1. Basic connectivity
        try:
            resp = self.client.get(url, timeout=8.0)
            result.reachable = True
            result.server_header = resp.headers.get("server", "")
            result.is_web_app = "text/html" in resp.headers.get("content-type", "")

            html = resp.text
            result.page_title = _extract_title(html)
            result.tech_stack = _detect_tech(resp.headers, html)

            # Detect embedded widgets
            result.detected_widgets = _detect_widgets(html)
            if result.detected_widgets:
                result.notes.append(f"Detected third-party chat widgets: {', '.join(result.detected_widgets)}")

            # Find inline API URLs from JS
            inline_endpoints = _extract_api_urls_from_js(html, base)
            for ep_url in inline_endpoints:
                result.found_endpoints.append(DiscoveredEndpoint(
                    url=ep_url,
                    format="openai" if "chat/completions" in ep_url else "custom_json",
                    confidence=0.6,
                    notes="Extracted from inline JavaScript",
                ))

        except httpx.RequestError as e:
            result.notes.append(f"Connectivity failed: {e}")
            return result

        # 2. Probe candidate paths
        for path in CANDIDATE_PATHS:
            ep = self._probe_path(base, path)
            if ep:
                result.found_endpoints.append(ep)

        # 3. Deduplicate and sort by confidence
        seen: set[str] = set()
        deduped = []
        for ep in sorted(result.found_endpoints, key=lambda e: e.confidence, reverse=True):
            if ep.url not in seen:
                seen.add(ep.url)
                deduped.append(ep)
        result.found_endpoints = deduped

        if not result.found_endpoints:
            result.notes.append(
                "No AI API endpoint found at this URL. "
                "The target may use a third-party chat widget (not directly testable via API) "
                "or may not have an exposed AI interface."
            )

        return result

    def _probe_path(self, base: str, path: str) -> Optional[DiscoveredEndpoint]:
        url = base + path

        # Quick HEAD probe first
        try:
            head = self.client.head(url, timeout=4.0)
            if head.status_code == 404:
                return None
        except Exception:
            pass

        # Try a minimal OpenAI-style POST
        try:
            resp = self.client.post(
                url,
                json={"model": "gpt-4", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=8.0,
            )
            ct = resp.headers.get("content-type", "")

            if resp.status_code == 200 and "json" in ct:
                body = resp.json()
                if "choices" in body or "message" in body or "content" in body or "response" in body:
                    return DiscoveredEndpoint(
                        url=url,
                        format="openai" if "choices" in body else "custom_json",
                        confidence=0.95,
                        probe_response=str(body)[:200],
                        notes=f"Responded with AI-like JSON on first probe",
                    )
                # Any 200+JSON at a chat path is suspicious
                return DiscoveredEndpoint(
                    url=url, format="custom_json", confidence=0.5,
                    probe_response=str(body)[:200],
                    notes="JSON response — may be AI endpoint",
                )

            if resp.status_code in (400, 422):
                # Server understood the request but rejected it — endpoint exists
                try:
                    err = resp.json()
                    if any(k in str(err).lower() for k in ["model", "message", "token", "api", "invalid"]):
                        return DiscoveredEndpoint(
                            url=url,
                            format="openai" if "choices" in path or "completions" in path else "custom_json",
                            confidence=0.75,
                            notes=f"Endpoint exists (HTTP {resp.status_code}) — authentication or format required",
                            auth_required=(resp.status_code == 401),
                        )
                except Exception:
                    pass
                return DiscoveredEndpoint(
                    url=url, format="custom_json", confidence=0.45,
                    notes=f"Endpoint exists (HTTP {resp.status_code})",
                )

            if resp.status_code == 401:
                return DiscoveredEndpoint(
                    url=url, format="openai", confidence=0.70,
                    auth_required=True,
                    notes="Endpoint exists but requires authentication",
                )

        except httpx.TimeoutException:
            # Timeout on a chat path is suspicious — might be processing a real LLM request
            return DiscoveredEndpoint(
                url=url, format="unknown", confidence=0.3,
                notes="Timed out — possible slow AI endpoint",
            )
        except Exception:
            pass

        return None

    def close(self) -> None:
        self.client.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip()[:120] if m else ""


def _detect_tech(headers: httpx.Headers, html: str) -> list[str]:
    tech: list[str] = []
    server = headers.get("server", "").lower()
    powered = headers.get("x-powered-by", "").lower()

    for sig, name in [("nginx", "Nginx"), ("apache", "Apache"), ("cloudflare", "Cloudflare"),
                      ("wordpress", "WordPress"), ("php", "PHP"), ("node", "Node.js"),
                      ("next", "Next.js"), ("react", "React"), ("vue", "Vue.js")]:
        if sig in server or sig in powered or sig in html.lower()[:3000]:
            tech.append(name)

    return list(dict.fromkeys(tech))


def _detect_widgets(html: str) -> list[str]:
    found: list[str] = []
    html_lower = html.lower()
    for name, pattern in THIRD_PARTY_WIDGETS.items():
        if re.search(pattern, html_lower):
            found.append(name)
    return found


def _extract_api_urls_from_js(html: str, base: str) -> list[str]:
    """Extract potential API URLs from inline JavaScript."""
    urls: list[str] = []

    # Find fetch/axios calls near "messages" or "chat"
    for pat in [
        r'fetch\s*\(\s*["\`]([^"\'`]+chat[^"\'`]*)["\`]',
        r'fetch\s*\(\s*["\`]([^"\'`]+api[^"\'`]*)["\`]',
        r'axios\s*\.\s*post\s*\(\s*["\`]([^"\'`]+)["\`]',
        r'url\s*:\s*["\`]([^"\'`]+(?:chat|message|completions)[^"\'`]*)["\`]',
    ]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            candidate = m.group(1)
            if candidate.startswith("http"):
                urls.append(candidate)
            elif candidate.startswith("/"):
                urls.append(base + candidate)

    return list(dict.fromkeys(urls))[:10]
