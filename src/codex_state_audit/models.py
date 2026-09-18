"""Shared data structures for the offline audit tool.

The types in this module deliberately describe observations rather than giving
special meaning to undocumented numeric signals.  In particular, 292 and 312
are represented as opaque labels by the validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EVIDENCE_LEVELS = (
    "observed_fixture",
    "document_claim",
    "hypothesis",
    "unknown",
    "not_observed",
)


@dataclass(frozen=True)
class Finding:
    """A safe-to-display finding.

    Findings contain a JSON path and a reason, never the original value.  This
    makes it safe to put them in a report even when a caller accidentally
    supplies an unredacted fixture.
    """

    path: str
    kind: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "kind": self.kind, "message": self.message}


@dataclass
class ValidationResult:
    """Result of validating and redacting one local fixture."""

    valid: bool
    safe_to_share: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    redacted_fixture: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "safe_to_share": self.safe_to_share,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "findings": [finding.as_dict() for finding in self.findings],
            "observations": self.observations,
            "evidence": self.evidence,
        }
