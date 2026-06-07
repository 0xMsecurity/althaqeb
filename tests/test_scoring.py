"""Tests for AIVSS+ scoring engine."""

import pytest
from althaqeb.utils.scoring import (
    calculate_aivss_plus,
    quick_score,
    AIVSSBaseMetrics,
    AIAmplifierMetrics,
    GCC_MULTIPLIERS,
)


def test_quick_score_returns_valid_range():
    result = quick_score()
    assert 0.0 <= result.final_score <= 10.0


def test_gcc_multiplier_increases_score():
    general = quick_score(gcc_context="general")
    critical = quick_score(gcc_context="critical_infra")
    assert critical.final_score >= general.final_score


def test_hajj_context_highest_multiplier():
    assert GCC_MULTIPLIERS["hajj_umrah"] == max(GCC_MULTIPLIERS.values())


def test_full_aivss_formula():
    base = AIVSSBaseMetrics(
        attack_vector=0.85,
        complexity=0.77,
        privileges=0.85,
        user_interaction=0.85,
        conf_impact=0.56,
        integrity_impact=0.56,
        avail_impact=0.56,
        ai_impact=0.5,
    )
    amp = AIAmplifierMetrics(
        autonomy=0.8,
        tool_scope=0.8,
        blast_radius=0.9,
        nondeterminism=0.5,
        self_mod=0.3,
    )
    result = calculate_aivss_plus(base, amp, gcc_context="financial_sama")
    assert result.final_score > 0
    assert result.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE")
    assert result.gcc_multiplier == 1.6


def test_max_score_capped_at_10():
    base = AIVSSBaseMetrics(
        attack_vector=1.0,
        complexity=1.0,
        privileges=1.0,
        user_interaction=1.0,
        conf_impact=1.0,
        integrity_impact=1.0,
        avail_impact=1.0,
        ai_impact=1.0,
    )
    amp = AIAmplifierMetrics(
        autonomy=1.0, tool_scope=1.0, blast_radius=1.0, nondeterminism=1.0, self_mod=1.0
    )
    result = calculate_aivss_plus(base, amp, gcc_context="hajj_umrah")
    assert result.final_score <= 10.0


def test_probabilistic_scoring():
    result = quick_score(attack_success_rate=0.9)
    assert result.probabilistic is not None
    assert result.probabilistic >= 0


def test_severity_labels():
    low = quick_score(attack_vector=0.2, autonomy=0.1, blast_radius=0.1)
    # Just verify we get a label
    assert low.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE")
