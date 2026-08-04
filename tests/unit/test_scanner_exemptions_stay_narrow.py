"""The two scanner exemptions stay one entry each, and stay narrow.

An allowlist is a place where a defect is permitted to live. Two exist in this repository,
both added on 2026-08-04 and both with a written reason:

* ``.trivyignore.yaml`` — limes' eval corpus ships inside the wheel, so the runtime image
  carries PEM armour whose body base64-decodes to "EXAMPLE ONLY - not a key". Trivy's secret
  scanner is right to report it; the durable fix is a limes wheel that does not ship its
  corpus. **The secret scanner stays on**: it found this on the first run it was ever given.
* ``.gitleaks.toml`` — ``.secrets.baseline`` stores SHA-1 digests of matched strings, which
  gitleaks reads as high-entropy generic keys (46 of them). The underlying strings are scanned
  at their own paths, so the exemption is derived-evidence-only.

Both are the kind of file nobody re-reads. This is what makes them loud if they grow: an
exemption that widens without anybody deciding to widen it is how a scanner stops scanning.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
_TRIVY = _REPO / ".trivyignore.yaml"
_GITLEAKS = _REPO / ".gitleaks.toml"


class TestTheTrivyExemption:
    def test_the_file_exists_and_parses(self) -> None:
        assert _TRIVY.is_file(), "the trivy ignore file is gone; so is its written justification"
        assert isinstance(yaml.safe_load(_TRIVY.read_text()), dict)

    def test_it_ignores_exactly_one_secret_rule_and_nothing_else(self) -> None:
        doc = yaml.safe_load(_TRIVY.read_text())
        assert set(doc) == {"secrets"}, (
            "the trivy ignore file grew a new section — vulnerabilities, misconfigurations and "
            f"licences are NOT exempted here, deliberately: {sorted(doc)}"
        )
        assert len(doc["secrets"]) == 1, f"more than one ignored secret rule: {doc['secrets']}"

    def test_the_single_entry_is_scoped_to_a_path_not_to_a_rule(self) -> None:
        entry = yaml.safe_load(_TRIVY.read_text())["secrets"][0]
        assert entry["id"] == "private-key"
        paths = entry["paths"]
        assert paths, "an id with no path silences that rule EVERYWHERE in the image"
        assert all(
            "limes/corpus" in p for p in paths
        ), f"the exemption reaches outside limes' corpus: {paths}"

    def test_it_carries_its_reason(self) -> None:
        text = _TRIVY.read_text()
        assert "EXAMPLE ONLY" in text, "the entry no longer states why the match is not a key"
        assert "limes" in text


class TestTheGitleaksExemption:
    def test_the_file_exists_and_parses(self) -> None:
        assert _GITLEAKS.is_file()
        assert isinstance(tomllib.loads(_GITLEAKS.read_text()), dict)

    def test_it_allowlists_exactly_one_path_on_one_rule(self) -> None:
        doc = tomllib.loads(_GITLEAKS.read_text())
        rules = doc.get("rules", [])
        assert len(rules) == 1, f"more than one gitleaks rule is customised: {rules}"
        assert rules[0]["id"] == "generic-api-key"
        paths = rules[0]["allowlist"]["paths"]
        assert paths == [
            r"^\.secrets\.baseline$"
        ], f"the gitleaks allowlist reaches beyond the detect-secrets baseline: {paths}"

    def test_it_keeps_the_default_rule_set(self) -> None:
        doc = tomllib.loads(_GITLEAKS.read_text())
        assert (
            doc["extend"]["useDefault"] is True
        ), "useDefault is off — every gitleaks rule but the one customised here is now silent"
