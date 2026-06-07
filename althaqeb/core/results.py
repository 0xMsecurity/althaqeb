"""Finding and result data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Finding:
    """A single vulnerability or observation from a scan."""

    technique:    str
    category:     str                   # injection / extraction / jailbreak / agent
    layer:        str                   # ATTACK / TRUST / DEFEND / INTEL / IDENTITY
    severity:     str                   # CRITICAL / HIGH / MEDIUM / LOW / INFO
    aivss_score:  float                 # 0.0 – 10.0
    confidence:   float                 # 0.0 – 1.0
    description:  str = ""
    payload:      str = ""
    response:     str = ""
    atlas_id:     Optional[str] = None  # MITRE ATLAS technique ID e.g. AML.T0051
    gcc_context:  str = "general"
    evidence:     dict[str, Any] = field(default_factory=dict)
    remediation:  str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique":   self.technique,
            "category":    self.category,
            "layer":       self.layer,
            "severity":    self.severity,
            "aivss_score": self.aivss_score,
            "confidence":  self.confidence,
            "description": self.description,
            "payload":     self.payload[:500] if self.payload else "",
            "response":    self.response[:500] if self.response else "",
            "atlas_id":    self.atlas_id,
            "gcc_context": self.gcc_context,
            "remediation": self.remediation,
        }
