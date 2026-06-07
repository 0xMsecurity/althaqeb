"""Core orchestration engine — ties together profiling, modules, and sessions."""

from __future__ import annotations

from typing import Any, Optional

from althaqeb.core.target import TargetProfiler
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
    # Full scan (all modules or a named one)
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

        modules_to_run = self._resolve_modules(module)

        for mod_name in modules_to_run:
            logger.info(f"Running module: [cyan]{mod_name}[/cyan]")
            try:
                findings = self._run_module(mod_name, url, api_key=api_key)
                for f in findings:
                    session.add_finding(f)
            except Exception as e:
                logger.warning(f"Module {mod_name} failed: {e}")

        session.complete()
        self.session_mgr.save(session)
        return session

    # ------------------------------------------------------------------
    # Single attack run
    # ------------------------------------------------------------------

    def run_attack(
        self,
        url: str,
        attack_type: str = "injection",
        api_key: Optional[str] = None,
    ) -> ScanSession:
        session = ScanSession(target_url=url, module=attack_type)

        try:
            findings = self._run_module(attack_type, url, api_key=api_key)
            for f in findings:
                session.add_finding(f)
        except Exception as e:
            logger.error(f"Attack module {attack_type} error: {e}")

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
    ) -> list[Finding]:
        if name == "injection":
            from althaqeb.modules.attack.injection import InjectionModule
            mod = InjectionModule(url, api_key=api_key, verbose=self.verbose)
            return mod.run()
        elif name == "extraction":
            from althaqeb.modules.attack.extraction import ExtractionModule
            mod = ExtractionModule(url, api_key=api_key, verbose=self.verbose)
            return mod.run()
        elif name == "jailbreak":
            from althaqeb.modules.attack.jailbreak import JailbreakModule
            mod = JailbreakModule(url, api_key=api_key, verbose=self.verbose)
            return mod.run()
        elif name == "agent":
            from althaqeb.modules.attack.agent import AgentAbuseModule
            mod = AgentAbuseModule(url, api_key=api_key, verbose=self.verbose)
            return mod.run()
        else:
            logger.warning(f"Unknown module: {name}")
            return []
