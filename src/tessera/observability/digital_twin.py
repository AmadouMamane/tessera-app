"""Assurance digital-twin scenarios for observability conformance."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.settings import LanguageCode, ObservabilityProfile

__all__ = ["TwinScenario", "run_assurance_twin"]


@dataclass(frozen=True, slots=True)
class TwinScenario:
    """One synthetic observability assurance scenario."""

    profile: str
    language: str
    observability_state: str
    risk_level: str
    expected_controls: tuple[str, ...]

    def model_dump(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "profile": self.profile,
            "language": self.language,
            "observability_state": self.observability_state,
            "risk_level": self.risk_level,
            "expected_controls": list(self.expected_controls),
        }


def run_assurance_twin() -> list[TwinScenario]:
    """Return the current V1/V2 simulation matrix for assurance checks."""
    scenarios: list[TwinScenario] = []
    for profile in (
        ObservabilityProfile.CLOUD_GCP_REGULATED,
        ObservabilityProfile.ON_PREM_STANDARD,
        ObservabilityProfile.ON_PREM_AIRGAPPED,
    ):
        for language in LanguageCode:
            scenarios.append(
                TwinScenario(
                    profile=profile.value,
                    language=language.value,
                    observability_state="healthy",
                    risk_level="high",
                    expected_controls=(
                        "privacy_gateway",
                        "guard_deny_audited",
                        "sensitive_action_proof_valid",
                        "evidence_bundle_committed",
                    ),
                )
            )
    return scenarios
