"""Shadow verification for observability evidence bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "VerificationFinding",
    "VerificationReport",
    "shadow_verify_recent",
    "verify_evidence_bundle",
]

_Severity = Literal["low", "medium", "high", "critical"]
_SIGNED_LEVELS = {"L3", "L4", "L5"}
_PROOF_REQUIRED_TOOLS = {"account_balance", "card_block"}
_FORBIDDEN_MARKERS = {"raw_prompt", "raw_completion", "access_token", "raw_account_id"}


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    """One assurance invariant finding from shadow verification."""

    code: str
    severity: _Severity
    message: str

    def model_dump(self) -> dict[str, str]:
        """Return a JSON-serializable representation."""
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Verification result for a single evidence bundle."""

    evidence_id: str | None
    status: Literal["pass", "warn", "fail"]
    findings: list[VerificationFinding] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "evidence_id": self.evidence_id,
            "status": self.status,
            "findings": [finding.model_dump() for finding in self.findings],
        }


def verify_evidence_bundle(bundle: Mapping[str, Any]) -> VerificationReport:
    """Verify core V1/V2 assurance invariants on an evidence bundle."""
    findings: list[VerificationFinding] = []
    encoded = json.dumps(bundle, default=str)
    for marker in _FORBIDDEN_MARKERS:
        if marker in encoded:
            findings.append(
                VerificationFinding(
                    code="forbidden_marker_present",
                    severity="critical",
                    message=f"forbidden telemetry marker {marker!r} is present",
                )
            )
    if bundle.get("privacy_status") != "redacted":
        findings.append(
            VerificationFinding(
                code="privacy_not_redacted",
                severity="critical",
                message="evidence bundle is not marked redacted",
            )
        )
    if bundle.get("assurance_level") in _SIGNED_LEVELS and not bundle.get("signature"):
        findings.append(
            VerificationFinding(
                code="bundle_unsigned",
                severity="high",
                message="verifiable/replayable profile emitted an unsigned bundle",
            )
        )
    for call in bundle.get("tool_calls", []) or []:
        if not isinstance(call, Mapping):
            continue
        if call.get("tool_name") in _PROOF_REQUIRED_TOOLS and not call.get("decision_proof_id"):
            findings.append(
                VerificationFinding(
                    code="tool_without_proof",
                    severity="high",
                    message=f"{call.get('tool_name')} lacks a decision proof",
                )
            )
    retrieval = bundle.get("retrieval_evidence", {})
    citation_count = len(bundle.get("citation_evidence", []) or [])
    if (
        isinstance(retrieval, Mapping)
        and int(retrieval.get("document_count", 0) or 0) > 0
        and citation_count == 0
    ):
        findings.append(
            VerificationFinding(
                code="retrieval_without_citation",
                severity="medium",
                message="retrieved documents are present but no citation evidence exists",
            )
        )
    for gap in bundle.get("evidence_gaps", []) or []:
        findings.append(
            VerificationFinding(
                code=str(gap),
                severity="medium",
                message=f"runtime reported evidence gap: {gap}",
            )
        )
    status: Literal["pass", "warn", "fail"] = "pass"
    if any(finding.severity in {"high", "critical"} for finding in findings):
        status = "fail"
    elif findings:
        status = "warn"
    return VerificationReport(
        evidence_id=str(bundle.get("evidence_id")) if bundle.get("evidence_id") else None,
        status=status,
        findings=findings,
    )


def shadow_verify_recent(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[VerificationReport]:
    """Verify the most recent persisted evidence bundles."""
    root = base_dir or get_settings().observability.evidence_dir
    if not root.exists():
        return []
    files = sorted(root.glob("*/*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    reports: list[VerificationReport] = []
    for path in files[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reports.append(
                VerificationReport(
                    evidence_id=path.stem,
                    status="fail",
                    findings=[
                        VerificationFinding(
                            code="bundle_unreadable",
                            severity="critical",
                            message="persisted bundle could not be parsed",
                        )
                    ],
                )
            )
            continue
        if isinstance(payload, dict):
            reports.append(verify_evidence_bundle(payload))
    return reports
