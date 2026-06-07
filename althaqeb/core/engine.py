"""Core orchestration engine — discovery, profiling, modules, sessions."""

from __future__ import annotations

from typing import Any, Optional

from althaqeb.core.target import TargetProfiler
from althaqeb.core.discovery import AIEndpointDiscovery, DiscoveryResult, DiscoveredEndpoint
from althaqeb.core.session import ScanSession, SessionManager
from althaqeb.core.results import Finding
from althaqeb.utils.logger import get_logger

logger = get_logger(__name__)


class Engine:
    """Central orchestrator for all Althaqeb scan operations."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.profiler = TargetProfiler()
        self.session_mgr = SessionManager()

    # ------------------------------------------------------------------
    # Target profiling
    # ------------------------------------------------------------------

    def profile_target(self, url: str, api_key: Optional[str] = None) -> dict[str, Any]:
        profile = self.profiler.profile(url, api_key=api_key)
        return profile.to_dict()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, url: str, api_key: Optional[str] = None) -> DiscoveryResult:
        disc = AIEndpointDiscovery(api_key=api_key)
        try:
            return disc.discover(url)
        finally:
            disc.close()

    # ------------------------------------------------------------------
    # Full scan
    # ------------------------------------------------------------------

    def run_scan(
        self,
        url: str,
        module: str = "all",
        api_key: Optional[str] = None,
        profile: Optional[dict] = None,
    ) -> ScanSession:
        session = ScanSession(target_url=url, module=module)
        if profile:
            session.profile = profile

        # Step 1: Discover the AI endpoint
        logger.info("[cyan]Discovering AI endpoint...[/cyan]")
        disc_result = self.discover(url, api_key=api_key)

        if not disc_result.reachable:
            logger.warning(f"[red]Target unreachable:[/red] {url}")
            session.complete()
            self.session_mgr.save(session)
            return session

        endpoint = disc_result.best_endpoint

        if endpoint:
            logger.info(f"[green]Found endpoint:[/green] {endpoint.url} (format={endpoint.format}, confidence={endpoint.confidence:.0%})")
        else:
            logger.warning("[yellow]No AI API endpoint discovered.[/yellow]")
            for note in disc_result.notes:
                logger.info(f"  {note}")
            if disc_result.detected_widgets:
                logger.info(f"  Detected widgets (not directly testable): {', '.join(disc_result.detected_widgets)}")

        # Step 2: Store discovery info in session profile
        session.profile.update({
            "discovery": {
                "reachable":         disc_result.reachable,
                "page_title":        disc_result.page_title,
                "server":            disc_result.server_header,
                "tech_stack":        disc_result.tech_stack,
                "detected_widgets":  disc_result.detected_widgets,
                "endpoint_found":    endpoint.url if endpoint else None,
                "endpoint_format":   endpoint.format if endpoint else None,
                "endpoint_confidence": endpoint.confidence if endpoint else 0.0,
                "notes":             disc_result.notes,
            }
        })

        # Step 3: Run modules if we have an endpoint
        if endpoint:
            modules_to_run = self._resolve_modules(module)
            for mod_name in modules_to_run:
                logger.info(f"Running module: [cyan]{mod_name}[/cyan]")
                try:
                    findings = self._run_module(mod_name, url, api_key=api_key, endpoint=endpoint)
                    for f in findings:
                        session.add_finding(f)
                except Exception as e:
                    logger.warning(f"Module {mod_name} error: {e}")
        else:
            # No direct API found — do passive analysis
            passive = self._passive_analysis(url, disc_result)
            for f in passive:
                session.add_finding(f)

        session.complete()
        self.session_mgr.save(session)
        return session

    # ------------------------------------------------------------------
    # Single attack
    # ------------------------------------------------------------------

    def run_attack(
        self,
        url: str,
        attack_type: str = "injection",
        api_key: Optional[str] = None,
    ) -> ScanSession:
        session = ScanSession(target_url=url, module=attack_type)

        disc_result = self.discover(url, api_key=api_key)
        endpoint = disc_result.best_endpoint

        session.profile["endpoint_found"] = endpoint.url if endpoint else None

        if endpoint:
            try:
                findings = self._run_module(attack_type, url, api_key=api_key, endpoint=endpoint)
                for f in findings:
                    session.add_finding(f)
            except Exception as e:
                logger.error(f"Attack module {attack_type} error: {e}")
        else:
            passive = self._passive_analysis(url, disc_result)
            for f in passive:
                session.add_finding(f)

        session.complete()
        self.session_mgr.save(session)
        return session

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_modules(self, module: str) -> list[str]:
        all_modules = ["injection", "extraction", "jailbreak"]
        if module == "all":
            return all_modules
        return [module]

    def _run_module(
        self,
        name: str,
        url: str,
        api_key: Optional[str] = None,
        endpoint: Optional[DiscoveredEndpoint] = None,
    ) -> list[Finding]:
        kwargs = dict(api_key=api_key, verbose=self.verbose, endpoint=endpoint)
        if name == "injection":
            from althaqeb.modules.attack.injection import InjectionModule
            return InjectionModule(url, **kwargs).run()
        elif name == "extraction":
            from althaqeb.modules.attack.extraction import ExtractionModule
            return ExtractionModule(url, **kwargs).run()
        elif name == "jailbreak":
            from althaqeb.modules.attack.jailbreak import JailbreakModule
            return JailbreakModule(url, **kwargs).run()
        elif name == "agent":
            from althaqeb.modules.attack.agent import AgentAbuseModule
            return AgentAbuseModule(url, **kwargs).run()
        else:
            logger.warning(f"Unknown module: {name}")
            return []

    def _passive_analysis(self, url: str, disc: DiscoveryResult) -> list[Finding]:
        """
        When no direct API is found, emit an INFO finding that describes
        what was discovered and recommends next steps.
        """
        from althaqeb.core.results import Finding
        findings = []

        if disc.detected_widgets:
            findings.append(Finding(
                technique="Third-Party Chat Widget Detected",
                category="discovery",
                layer="ATTACK",
                severity="INFO",
                aivss_score=0.0,
                confidence=0.8,
                description=(
                    f"The following third-party chat/AI widgets were detected on {url}: "
                    f"{', '.join(disc.detected_widgets)}. "
                    f"These widgets relay traffic to external AI providers. "
                    f"Direct API injection is not possible without the provider API key, "
                    f"but social engineering and indirect injection via chat UI are viable."
                ),
                remediation=(
                    "Review third-party widget permissions. Ensure vendor AI systems apply "
                    "input validation. Consider widget isolation with a strict CSP."
                ),
            ))

        if not disc.found_endpoints and disc.reachable:
            findings.append(Finding(
                technique="No Exposed AI API Endpoint",
                category="discovery",
                layer="ATTACK",
                severity="INFO",
                aivss_score=0.0,
                confidence=1.0,
                description=(
                    f"No AI API endpoint was found at {url} via automated discovery. "
                    f"The target may: (1) use a third-party widget not exposing a direct API, "
                    f"(2) require authentication headers not provided, "
                    f"(3) use a non-standard API path, or "
                    f"(4) not have an AI interface at this URL. "
                    f"Tech detected: {', '.join(disc.tech_stack) or 'unknown'}. "
                    f"Provide --api-key or specify the exact API path with --target pointing directly at the endpoint."
                ),
                remediation="Point the scanner directly at the AI API endpoint (e.g. https://site.com/api/chat).",
            ))

        return findings
