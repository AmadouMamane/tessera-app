"""Hica external opposability seal — periodic third-party attestation of the ledger HEAD.

ADR 0015 §Amendment 3 pt3 + §Correction 3c pt4 + rails register §9.
Design note: ``docs/decisions/0022-hica-seal-design-note.md``.

The seal is an **opposability enrichment, never the store**: it attests the chain head, it never
holds ledger content. *Owned first, sealed second.* Its two jobs:

* **Third-party opposability** — a verified external attestation (an RFC 3161 timestamp token) of
  the head lets an auditor prove, **outside Tessera** (``openssl ts -verify``, offline, no Tessera
  code), that the chain existed at a given time.
* **Time-bound divergence detection** (§Correction 3c pt4) — sealing the head every ``τ`` bounds the
  window in which a fork/rewrite could go undetected to one interval: a fork moves the head lineage,
  so the next cycle's continuity check flags it.

Honesty is **structural**, not a convention: the default provider is :class:`NoOpProvider`, which
**cannot mint a token**, so the badge can never read "Scellé" without a real, verified attestation.
The badge is recomputed live from a cryptographic verification, never stored (register §9,
"jamais cosmétique"). It **composes with** the tree-aware verifier
(``content_integrity`` / ``linear`` / ``attested``); it never replaces it.
"""

from __future__ import annotations

import base64
import os
import subprocess  # the RFC 3161 provider shells out to openssl (configured path only)
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from urllib.parse import urlparse

from tessera.guard.audit import LEDGER_SEAL_TYPE, SEAL_ACTOR, emit_ledger_seal
from tessera.guard.ledger_store import (
    LedgerTreeStatus,
    ledger_source,
    load_ledger_payloads_of_type,
    load_ledger_payloads_sync,
    read_ledger_entries,
    verify_ledger_tree,
)
from tessera.urlfetch import urlopen_http

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from tessera.settings import Settings

__all__ = [
    "BadgeState",
    "ResolvedBadge",
    "SealCycleResult",
    "SealProvider",
    "SealStatus",
    "SealToken",
    "SealUnavailableError",
    "SealVerification",
    "active_ledger_opposability",
    "active_ledger_seal_status",
    "evaluate_seal",
    "get_seal_provider",
    "run_seal_cycle",
    "seal_badge",
    "seal_posture",
    "validate_exposed_seal_config",
]

_GENESIS = "0" * 64

# The badge states of register §9, tree-aware. The backend always resolves to one of these four;
# "verification_en_cours" is a *frontend* transient (the query is in flight) folded into the union.
ResolvedBadge = Literal[
    "non_scelle",
    "scelle_opposable",
    "scelle_non_qualifie",
    "integrite_partielle",
]
BadgeState = Literal[
    "non_scelle",
    "scelle_opposable",
    "scelle_non_qualifie",
    "integrite_partielle",
    "verification_en_cours",
]

# The seal facet — what a live verification of the latest seal entry says.
SealState = Literal["absent", "verified", "stale", "unverifiable", "divergent"]


# ── Provider contract ─────────────────────────────────────────────────────────


class SealUnavailableError(RuntimeError):
    """No seal service is configured/reachable — the honest reason a head could not be sealed."""


@dataclass(frozen=True, slots=True)
class SealToken:
    """A provider-specific external attestation of one head hash (opaque to the rest of Tessera)."""

    sealed_head: str
    sealed_at: str  # ISO-8601, from the TOKEN (the TSA's clock), not ours
    provider: str
    qualified: bool
    tsa: str | None
    material: str  # base64 of the externally-verifiable artifact (the RFC 3161 token)


@dataclass(frozen=True, slots=True)
class SealVerification:
    """The result of re-verifying a token cryptographically, offline, against the trust root."""

    verified: bool
    qualified: bool
    provider: str
    sealed_head: str | None
    sealed_at: str | None
    reason: str | None = None


@runtime_checkable
class SealProvider(Protocol):
    """A third-party seal anchor. ``seal`` obtains a fresh attestation; ``verify`` re-checks one."""

    name: str
    qualified: bool

    def seal(self, head_hash: str) -> SealToken:
        """Obtain a fresh external attestation of ``head_hash``."""
        ...

    def verify(self, token: SealToken, head_hash: str) -> SealVerification:
        """Re-verify ``token`` against the trust root, offline."""
        ...


class NoOpProvider:
    """The default — no seal service. It CANNOT mint a token (the honesty invariant, R7).

    Every current environment runs this until a real TSA is wired, so the badge is honestly
    «Intégrité partielle» (never a cosmetic green).
    """

    name = "none"
    qualified = False

    def seal(self, head_hash: str) -> SealToken:  # noqa: ARG002  Protocol shape; head unused
        raise SealUnavailableError("no seal provider configured (seal_provider='none')")

    def verify(self, token: SealToken, head_hash: str) -> SealVerification:  # noqa: ARG002
        return SealVerification(
            verified=False,
            qualified=False,
            provider=self.name,
            sealed_head=token.sealed_head,
            sealed_at=token.sealed_at,
            reason="no seal provider configured",
        )


class Rfc3161Provider:
    """RFC 3161 Time-Stamp Authority anchor (the recommended real provider — design note §4).

    ``seal`` builds a timestamp query over the head hash, POSTs it to the TSA, and keeps the reply
    (the TST). ``verify`` re-validates the TST offline against the pinned CA cert — the same check a
    third party runs with ``openssl ts -verify``, so the attestation is opposable outside Tessera.
    Only instantiated when ``seal_provider='rfc3161'``; its network/exec path is exercised by the
    Lot 3 integration/manual verification, never by the hermetic unit suite.
    """

    name = "rfc3161"

    def __init__(self, *, url: str | None, cert: Path | None, qualified: bool) -> None:
        self._url = url
        self._cert = cert
        self.qualified = qualified

    def seal(self, head_hash: str) -> SealToken:
        if not self._url:
            raise SealUnavailableError("seal_tsa_url is not configured")
        query = self._openssl(["ts", "-query", "-digest", head_hash, "-sha256", "-cert"])
        token = self._post(query)
        sealed_at = self._token_time(token)
        return SealToken(
            sealed_head=head_hash,
            sealed_at=sealed_at,
            provider=self.name,
            qualified=self.qualified,
            tsa=self._url,
            material=base64.b64encode(token).decode("ascii"),
        )

    def verify(self, token: SealToken, head_hash: str) -> SealVerification:
        if self._cert is None:
            return self._fail(token, "seal_tsa_cert is not configured")
        try:
            reply = base64.b64decode(token.material)
        except (ValueError, TypeError) as exc:
            return self._fail(token, f"undecodable token: {exc}")
        with tempfile.NamedTemporaryFile(suffix=".tsr") as tsr:
            tsr.write(reply)
            tsr.flush()
            argv = [
                "openssl",
                "ts",
                "-verify",
                "-digest",
                head_hash,
                "-in",
                tsr.name,
                "-CAfile",
                str(self._cert),
            ]
            proc = subprocess.run(argv, capture_output=True, check=False)  # noqa: S603  fixed argv
        ok = proc.returncode == 0
        return SealVerification(
            verified=ok,
            qualified=self.qualified and ok,
            provider=self.name,
            sealed_head=token.sealed_head,
            sealed_at=token.sealed_at,
            reason=None
            if ok
            else proc.stderr.decode("utf-8", "replace").strip() or "verify failed",
        )

    def _fail(self, token: SealToken, reason: str) -> SealVerification:
        return SealVerification(
            verified=False,
            qualified=False,
            provider=self.name,
            sealed_head=token.sealed_head,
            sealed_at=token.sealed_at,
            reason=reason,
        )

    def _openssl(self, args: list[str]) -> bytes:
        argv = ["openssl", *args]
        proc = subprocess.run(argv, capture_output=True, check=True)  # noqa: S603  fixed argv
        return proc.stdout

    def _post(self, query: bytes) -> bytes:
        req = urllib.request.Request(  # noqa: S310  scheme gated by `urlopen_http` below
            self._url or "",
            data=query,
            headers={"Content-Type": "application/timestamp-query"},
            method="POST",
        )
        with urlopen_http(req, timeout=15) as resp:
            return bytes(resp.read())

    def _token_time(self, token: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".tsr") as tsr:
            tsr.write(token)
            tsr.flush()
            text = self._openssl(["ts", "-reply", "-in", tsr.name, "-text"]).decode(
                "utf-8", "replace"
            )
        for line in text.splitlines():
            if line.strip().lower().startswith("time stamp:"):
                return line.split(":", 1)[1].strip()
        return datetime.now(UTC).isoformat()


def get_seal_provider(settings: Settings | None = None) -> SealProvider:
    """The configured seal provider — :class:`NoOpProvider` unless a real one is wired (R7)."""
    from tessera.settings import get_settings

    guard = (settings or get_settings()).guard
    if guard.seal_provider == "rfc3161":
        return Rfc3161Provider(
            url=guard.seal_tsa_url, cert=guard.seal_tsa_cert, qualified=guard.seal_tsa_qualified
        )
    return NoOpProvider()


def seal_posture(settings: Settings | None = None) -> dict[str, object]:
    """The seal's boot posture — one honest log line + the scheduler's start decision.

    Under ``provider='none'`` (the default) ``sealing`` is False: nothing is scheduled and the badge
    honestly stays «Intégrité partielle». A real provider reports its name, qualification, and the
    cadence τ. This is the only place that decides "are we sealing?" so the log line and the
    scheduler can never disagree.
    """
    from tessera.settings import get_settings

    guard = (settings or get_settings()).guard
    provider = get_seal_provider(settings)
    sealing = not isinstance(provider, NoOpProvider)
    return {
        "provider": provider.name,
        "qualified": bool(getattr(provider, "qualified", False)),
        "sealing": sealing,
        "cadence_s": guard.seal_interval_s if sealing else None,
    }


def validate_exposed_seal_config(settings: Settings | None = None) -> None:
    """Refuse an exposed deployment that cannot earn the infalsifiability claim.

    Local development and CI deliberately keep the honest ``none`` provider.  Staging and
    production are public proof surfaces: ADR 0042 requires a qualified RFC 3161 provider, an
    HTTPS endpoint, a readable pinned trust root, and bounded verification/seal cadences.  This
    validates *posture*, not provider availability; the live badge still requires a successfully
    re-verified token and therefore can never become cosmetic.

    Raises:
        RuntimeError: If an exposed environment cannot produce and verify qualified seals.
    """
    from tessera.settings import Environment, get_settings

    resolved = settings or get_settings()
    if resolved.environment not in {Environment.STAGING, Environment.PRODUCTION}:
        return

    guard = resolved.guard
    errors: list[str] = []
    if guard.seal_provider != "rfc3161":
        errors.append("TESSERA_GUARD__SEAL_PROVIDER must be 'rfc3161'")

    tsa_url = guard.seal_tsa_url or ""
    parsed = urlparse(tsa_url)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append("TESSERA_GUARD__SEAL_TSA_URL must be an absolute HTTPS URL")

    cert = guard.seal_tsa_cert
    if cert is None or not cert.is_file() or not os.access(cert, os.R_OK):
        errors.append("TESSERA_GUARD__SEAL_TSA_CERT must be a readable pinned trust-root file")

    if not guard.seal_tsa_qualified:
        errors.append("TESSERA_GUARD__SEAL_TSA_QUALIFIED must be true for a qualified EU TSA")
    if guard.seal_interval_s <= 0:
        errors.append("TESSERA_GUARD__SEAL_INTERVAL_S must be positive")
    if not guard.seal_interval_s <= guard.seal_staleness_budget_s <= 2 * guard.seal_interval_s:
        errors.append(
            "TESSERA_GUARD__SEAL_STALENESS_BUDGET_S must be between one and two seal intervals"
        )
    if not 0 < guard.ledger_verify_interval_s <= guard.seal_interval_s:
        errors.append(
            "TESSERA_GUARD__LEDGER_VERIFY_INTERVAL_S must be positive and no greater than the "
            "seal interval"
        )

    if errors:
        details = "; ".join(errors)
        raise RuntimeError(
            "Exposed Tessera deployments must earn the externally verifiable "
            f"'registre infalsifiable' claim (ADR 0042): {details}."
        )


# ── Evaluation (display side — pure, cached, live) ──────────────────────────────


@dataclass(frozen=True, slots=True)
class SealStatus:
    """A live verdict on the latest seal entry — the enrichment layered onto the tree verdict."""

    state: SealState
    provider: str | None
    qualified: bool
    sealed_head: str | None
    sealed_at: str | None
    reason: str | None = None


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def latest_seal_entry(
    payloads: Sequence[Mapping[str, object]], *, at: datetime | None = None
) -> Mapping[str, object] | None:
    """The most recent ``tessera.ledger.seal`` entry (≤ ``at`` if given), or None."""
    found: Mapping[str, object] | None = None
    for payload in payloads:
        if payload.get("type") != LEDGER_SEAL_TYPE:
            continue
        if at is not None:
            sealed_at = _parse_iso(payload.get("sealed_at"))
            if sealed_at is not None and sealed_at > at:
                continue
        found = payload
    return found


def _token_from_entry(entry: Mapping[str, object]) -> SealToken:
    tsa = entry.get("tsa")
    return SealToken(
        sealed_head=str(entry.get("sealed_head", "")),
        sealed_at=str(entry.get("sealed_at", "")),
        provider=str(entry.get("provider", "")),
        qualified=bool(entry.get("qualified", False)),
        tsa=tsa if isinstance(tsa, str) else None,
        material=str(entry.get("token_b64", "")),
    )


def evaluate_seal(
    payloads: Sequence[Mapping[str, object]],
    *,
    provider: SealProvider,
    now: datetime,
    staleness_budget_s: int,
    at: datetime | None = None,
) -> SealStatus:
    """Live seal verdict over the ledger payloads (as of ``at`` if given).

    Honesty short-circuit: with the NoOp provider there is no trust root to verify against, so the
    result is ``absent`` regardless of any entries — the badge can never go green (R7). Otherwise
    the latest seal entry's token is re-verified cryptographically; a token that fails is
    ``unverifiable``, a divergence-flagged seal is ``divergent``, and a seal older than the
    staleness budget is ``stale`` (the §Correction 3c detection guarantee has lapsed).
    """
    if isinstance(provider, NoOpProvider):
        return SealStatus("absent", None, False, None, None, "no seal provider configured")
    entry = latest_seal_entry(payloads, at=at)
    if entry is None:
        return SealStatus("absent", provider.name, False, None, None, "no seal entry yet")
    token = _token_from_entry(entry)
    verification = provider.verify(token, token.sealed_head)
    if not verification.verified:
        return SealStatus(
            "unverifiable",
            provider.name,
            False,
            token.sealed_head,
            token.sealed_at,
            verification.reason,
        )
    if bool(entry.get("divergence")):
        return SealStatus(
            "divergent",
            provider.name,
            verification.qualified,
            token.sealed_head,
            token.sealed_at,
            "head continuity broke since the previous seal",
        )
    sealed_at = _parse_iso(entry.get("sealed_at"))
    if sealed_at is not None and (now - sealed_at).total_seconds() > staleness_budget_s:
        return SealStatus(
            "stale",
            provider.name,
            verification.qualified,
            token.sealed_head,
            token.sealed_at,
            "seal is stale",
        )
    return SealStatus(
        "verified", provider.name, verification.qualified, token.sealed_head, token.sealed_at, None
    )


def seal_badge(tree: LedgerTreeStatus, seal: SealStatus) -> ResolvedBadge:
    """Compose the tree verdict and the seal verdict into the register §9 badge (design note §6).

    "chaîne rompue" = ``content_integrity`` false (a fork is a tree, not a break). "Scellé ·
    opposable" is earned only by a **verified + qualified** seal over a linear-or-attested chain;
    a verified non-qualified seal is "Scellé (non qualifié)"; a fresh unattested fork downgrades to
    «Intégrité partielle» even under a valid seal (Q3).
    """
    if not tree.content_integrity:
        return "non_scelle"
    if seal.state == "verified" and (tree.linear or tree.attested):
        return "scelle_opposable" if seal.qualified else "scelle_non_qualifie"
    return "integrite_partielle"


# ── Active-ledger reads (both mediums, honest-empty on unreachable) ─────────────


def _read_active_payloads(
    path: Path | None = None, *, at: datetime | None = None
) -> list[dict[str, object]]:
    """Active-ledger payloads (oldest→newest), optionally as of ``at``. Raises if pg unreachable."""
    if ledger_source() == "postgres":
        return load_ledger_payloads_sync(at.isoformat() if at else None)
    entries = read_ledger_entries(path)
    if at is None:
        return entries
    return [e for e in entries if (_parse_iso(e.get("occurred_at")) or at) <= at]


def active_ledger_seal_status(
    path: Path | None = None, *, at: datetime | None = None
) -> SealStatus:
    """Seal facet of the active ledger (footer suffix + ``/audit/integrity`` seal fields).

    Two reads that were pure waste, both on the badge's hot path:

    * Under the NoOp provider (the shipped default) ``evaluate_seal`` returns ``absent`` without
      ever looking at a payload — yet this function loaded all 25 634 of them first, and threw
      them away. The provider decision now happens BEFORE the read.
    * When a provider IS configured, the seal only needs ``tessera.ledger.seal`` entries — a
      handful. It now asks for those, instead of every row in the ledger.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    provider = get_seal_provider(settings)
    now = datetime.now(UTC)
    if isinstance(provider, NoOpProvider):
        # The honesty short-circuit in evaluate_seal, hoisted above the read it made pointless.
        return evaluate_seal(
            (),
            provider=provider,
            now=now,
            staleness_budget_s=settings.guard.seal_staleness_budget_s,
            at=at,
        )
    payloads: Sequence[Mapping[str, object]]
    if ledger_source() == "postgres":
        payloads = load_ledger_payloads_of_type(LEDGER_SEAL_TYPE, at.isoformat() if at else None)
    else:
        payloads = _read_active_payloads(path, at=at)
    return evaluate_seal(
        payloads,
        provider=provider,
        now=now,
        staleness_budget_s=settings.guard.seal_staleness_budget_s,
        at=at,
    )


def active_ledger_opposability(
    path: Path | None = None, *, at: datetime | None = None
) -> dict[str, object]:
    """The full TE-01 / État à date opposability verdict as of ``at`` (badge + tree + seal facts).

    One read of the payloads ≤ T → ``verify_ledger_tree`` (content/order) + ``evaluate_seal``
    (third-party) → the register §9 badge. Every field is computed live; nothing is stored
    (register §9, "jamais cosmétique"). Raises on an unreachable ledger — the caller degrades to the
    honest "Vérification en cours", never a fabricated green.

    It re-walks the whole chain, and it keeps doing so. This is the verdict of the page that
    asserts opposability to a regulator; the cost of that assertion is reading what it asserts
    about. What was wrong was not this function — it was the **fleet's health dot and the header
    bell calling it** to extract one boolean, and paying for a full re-hash plus a seal
    evaluation they discarded. Those two now ask
    :func:`tessera.guard.ledger_checkpoint.active_ledger_verdict` and
    :func:`active_ledger_seal_status`, which answer their weaker question at their weaker price.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    provider = get_seal_provider(settings)
    payloads = _read_active_payloads(path, at=at)
    tree = verify_ledger_tree(payloads)
    seal = evaluate_seal(
        payloads,
        provider=provider,
        now=datetime.now(UTC),
        staleness_budget_s=settings.guard.seal_staleness_budget_s,
        at=at,
    )
    return {
        "badge": seal_badge(tree, seal),
        "content_integrity": tree.content_integrity,
        "linear": tree.linear,
        "attested": tree.attested,
        "fork_count": tree.fork_count,
        "orphan_count": tree.orphan_count,
        "length": tree.length,
        "seal_state": seal.state,
        "seal_provider": seal.provider,
        "seal_qualified": seal.qualified,
        "sealed_at": seal.sealed_at,
        "sealed_head": seal.sealed_head,
    }


# ── Seal cycle (writer side — off-chrono, never on a request path) ──────────────


@dataclass(frozen=True, slots=True)
class SealCycleResult:
    """What one seal cycle did — for the scheduler's log and the divergence monitor."""

    sealed: bool
    state: Literal["sealed", "unavailable", "empty"]
    head: str | None
    prev_head: str | None
    continuity: Literal["genesis", "continuous", "divergent", "rewrite"]
    sealed_at: str | None = None


def _head_continuity(
    payloads: Sequence[Mapping[str, object]], prev_head: str | None, head: str | None
) -> Literal["genesis", "continuous", "divergent", "rewrite"]:
    """Walk ``prev_head → head`` over present rows to classify continuity.

    A fork on the path (or a missing ``prev_head``) is the §Correction 3c pt4 divergence signal —
    bounded to one interval by the cycle cadence.
    """
    if prev_head is None:
        return "genesis"
    by_hash: dict[str, Mapping[str, object]] = {}
    children: dict[str, list[str]] = {}
    for payload in payloads:
        stored = payload.get("hash")
        if not isinstance(stored, str):
            continue
        by_hash[stored] = payload
        children.setdefault(str(payload.get("prev_hash", "")), []).append(stored)
    if prev_head not in by_hash:
        return "rewrite"  # a previously-sealed head vanished — provable tampering
    current = prev_head
    while current != head:
        kids = children.get(current, [])
        if len(kids) != 1:
            return "divergent"  # a fork (≥2) or a dead end (0) between the two seals
        current = kids[0]
    return "continuous"


def run_seal_cycle(
    *, provider: SealProvider | None = None, path: Path | None = None
) -> SealCycleResult:
    """One periodic seal of the current head (design note §5.3).

    Reads the head, checks continuity against the last sealed head, obtains a fresh attestation, and
    appends ONE ``tessera.ledger.seal`` entry through the serialized writer. If the provider is
    unavailable, **no entry is appended** — the badge honestly stays «Intégrité partielle» until a
    real seal lands (no placeholder, R2/R3/H3). A broken continuity is recorded on the entry
    (``divergence=True``) rather than papered over.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved = provider or get_seal_provider(settings)
    payloads = _read_active_payloads(path)
    head = str(payloads[-1].get("hash", "")) if payloads else None
    if not head:
        return SealCycleResult(False, "empty", None, None, "genesis")
    prev_entry = latest_seal_entry(payloads)
    prev_head = str(prev_entry.get("sealed_head")) if prev_entry else None
    continuity = _head_continuity(payloads, prev_head, head)
    try:
        token = resolved.seal(head)
    except SealUnavailableError:
        return SealCycleResult(False, "unavailable", head, prev_head, continuity)
    emit_ledger_seal(
        sealed_head=head,
        prev_sealed_head=prev_head,
        provider=token.provider,
        tsa=token.tsa,
        token_b64=token.material,
        sealed_at=token.sealed_at,
        qualified=token.qualified,
        divergence=continuity in {"divergent", "rewrite"},
        # The off-chronology cycle sealed the head; no operator asked for this one.
        actor=SEAL_ACTOR,
    )
    return SealCycleResult(True, "sealed", head, prev_head, continuity, token.sealed_at)
