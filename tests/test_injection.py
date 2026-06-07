"""Tests for injection module payload loading and marker detection."""

import json
import pytest
from pathlib import Path


PAYLOADS_DIR = Path(__file__).parent.parent / "althaqeb" / "payloads"


def test_direct_payloads_load():
    path = PAYLOADS_DIR / "injection" / "direct.json"
    assert path.exists(), "direct.json payload file missing"
    data = json.loads(path.read_text())
    assert len(data) >= 10
    for item in data:
        assert "payload" in item
        assert "name" in item
        assert "id" in item


def test_multilingual_payloads_load():
    path = PAYLOADS_DIR / "injection" / "multilingual.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) >= 5
    arabic_found = any(p.get("language", "").startswith("ar") for p in data)
    assert arabic_found, "Should have Arabic language payloads"


def test_extraction_payloads_load():
    path = PAYLOADS_DIR / "extraction" / "system_prompt.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) >= 10


def test_jailbreak_payloads_load():
    path = PAYLOADS_DIR / "jailbreak" / "techniques.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) >= 8
    severities = {p.get("severity") for p in data if "severity" in p}
    assert "HIGH" in severities


def test_injection_success_markers():
    """InjectionModule._measure_success detects marker hits correctly."""
    from althaqeb.modules.attack.injection import InjectionModule
    assert InjectionModule._measure_success("INJECTION_SUCCESS here", ["INJECTION_SUCCESS"]) > 0.5
    assert InjectionModule._measure_success("I cannot do that", ["INJECTION_SUCCESS"]) == 0.0


def test_jailbreak_success_markers():
    """JailbreakModule._measure_jailbreak_success rejects refusals."""
    from althaqeb.modules.attack.jailbreak import JailbreakModule
    assert JailbreakModule._measure_jailbreak_success("I cannot help with that", ["DAN"]) == 0.0
    assert JailbreakModule._measure_jailbreak_success("DAN mode enabled", ["DAN"]) > 0.0
