"""AIVSS+ scoring engine — extends OWASP AIVSS v0.8 with GCC context multipliers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# GCC Context Multipliers (from start.txt design document)
# ---------------------------------------------------------------------------
GCC_MULTIPLIERS = {
    "hajj_umrah":        2.0,   # Hajj/Umrah platform — mass-scale religious harm potential
    "critical_infra":    1.8,   # Critical infrastructure (power, water, oil)
    "financial_sama":    1.6,   # Financial services under SAMA/CBB regulation
    "gov_eservices":     1.5,   # Government e-services and national ID systems
    "healthcare":        1.4,   # Healthcare AI (patient harm potential)
    "education":         1.2,   # Education platforms (minor protection)
    "general":           1.0,   # General-purpose applications
}


@dataclass
class AIVSSBaseMetrics:
    """OWASP AIVSS v0.8 base metrics — mapped to 0.0–1.0 scale."""
    attack_vector:    float = 0.85   # Network=0.85 / Adjacent=0.62 / Local=0.55 / Physical=0.20
    complexity:       float = 0.77   # Low=0.77 / High=0.44
    privileges:       float = 0.85   # None=0.85 / Low=0.62 / High=0.27
    user_interaction: float = 0.85   # None=0.85 / Required=0.62
    conf_impact:      float = 0.56   # None=0.00 / Low=0.22 / High=0.56
    integrity_impact: float = 0.56
    avail_impact:     float = 0.56
    ai_impact:        float = 0.50   # Unique to AIVSS — model compromise, hallucination injection


@dataclass
class AIAmplifierMetrics:
    """AI-specific amplifier factors (AIVSS+ extension)."""
    autonomy:       float = 0.5   # How autonomous is the agent? 0.0–1.0
    tool_scope:     float = 0.5   # How many/dangerous are available tools? 0.0–1.0
    blast_radius:   float = 0.5   # Impact breadth across users/systems 0.0–1.0
    nondeterminism: float = 0.3   # Reproducibility factor 0.0–1.0
    self_mod:       float = 0.0   # Can the model modify its own instructions? 0.0–1.0


@dataclass
class AIVSSScore:
    base_score:      float = 0.0
    ai_amplifier:    float = 0.0
    raw_score:       float = 0.0
    gcc_multiplier:  float = 1.0
    final_score:     float = 0.0
    severity:        str   = "NONE"
    gcc_context:     str   = "general"
    probabilistic:   Optional[float] = None


def calculate_aivss_plus(
    base: AIVSSBaseMetrics,
    amplifier: AIAmplifierMetrics,
    gcc_context: str = "general",
    attack_success_rate: Optional[float] = None,
) -> AIVSSScore:
    """
    AIVSS+ scoring formula from Althaqeb design document.

    BaseScore   = (AV×0.25) + (C×0.15) + (P×0.15) + (UI×0.10) +
                  (ConfI×0.10) + (IntI×0.10) + (AvailI×0.10) + (AIImpact×0.05)
    AIAmplifier = (Autonomy×0.30) + (ToolScope×0.30) + (BlastRadius×0.20) +
                  (Nondeterminism×0.10) + (SelfMod×0.10)
    RawScore    = (BaseScore×0.55) + (AIAmplifier×0.45)
    FinalScore  = min(10.0, RawScore×10 × GCC_Multiplier)
    """
    base_score = (
        base.attack_vector    * 0.25 +
        base.complexity       * 0.15 +
        base.privileges       * 0.15 +
        base.user_interaction * 0.10 +
        base.conf_impact      * 0.10 +
        base.integrity_impact * 0.10 +
        base.avail_impact     * 0.10 +
        base.ai_impact        * 0.05
    )

    ai_amp = (
        amplifier.autonomy       * 0.30 +
        amplifier.tool_scope     * 0.30 +
        amplifier.blast_radius   * 0.20 +
        amplifier.nondeterminism * 0.10 +
        amplifier.self_mod       * 0.10
    )

    raw_score = (base_score * 0.55) + (ai_amp * 0.45)
    gcc_mult  = GCC_MULTIPLIERS.get(gcc_context, 1.0)
    final     = min(10.0, raw_score * 10.0 * gcc_mult)

    probabilistic: Optional[float] = None
    if attack_success_rate is not None:
        rate = max(attack_success_rate, 0.01)
        probabilistic = min(10.0, final * (1 + math.log10(rate)))

    severity = _severity_label(final)

    return AIVSSScore(
        base_score=round(base_score * 10, 2),
        ai_amplifier=round(ai_amp * 10, 2),
        raw_score=round(raw_score * 10, 2),
        gcc_multiplier=gcc_mult,
        final_score=round(final, 1),
        severity=severity,
        gcc_context=gcc_context,
        probabilistic=round(probabilistic, 1) if probabilistic is not None else None,
    )


def quick_score(
    attack_vector: float = 0.85,
    autonomy: float = 0.5,
    blast_radius: float = 0.5,
    gcc_context: str = "general",
    attack_success_rate: Optional[float] = None,
) -> AIVSSScore:
    """Quick scoring with sensible defaults for most findings."""
    base = AIVSSBaseMetrics(attack_vector=attack_vector)
    amp  = AIAmplifierMetrics(autonomy=autonomy, blast_radius=blast_radius)
    return calculate_aivss_plus(base, amp, gcc_context, attack_success_rate)


def _severity_label(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    elif score >= 7.0:
        return "HIGH"
    elif score >= 4.0:
        return "MEDIUM"
    elif score > 0.0:
        return "LOW"
    return "NONE"
