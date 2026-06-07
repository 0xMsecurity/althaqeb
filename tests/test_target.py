"""Tests for target profiling."""

import pytest
from althaqeb.core.target import TargetProfile, TargetProfiler


def test_target_profile_to_dict():
    profile = TargetProfile(url="https://example.com", reachable=True, api_type="openai-compat")
    d = profile.to_dict()
    assert d["url"] == "https://example.com"
    assert d["reachable"] is True
    assert d["api_type"] == "openai-compat"


def test_profile_unreachable_target():
    profiler = TargetProfiler(timeout=2.0)
    result = profiler.profile("http://127.0.0.1:19999")  # Nothing running here
    assert result.reachable is False
    assert result.url == "http://127.0.0.1:19999"


def test_target_profile_defaults():
    p = TargetProfile(url="http://test.local")
    assert p.api_type is None
    assert p.reachable is False
    assert p.has_system_prompt is False
    assert p.language_support == ["en"]
