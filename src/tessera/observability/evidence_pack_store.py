"""Durable evidence packs (create-the-source, page #15).

The Proofs page described an evidence-pack subsystem that did not exist; this
module IS its real, honestly-scoped core. A pack is a **manifest**, not a
container: it freezes, at creation time, the counts and integrity verdict of
every durable proof store this build owns (hash-chained audit ledger, eval
scores, replay bundles, eval reports), stamps WHO created it (verified
assertion principal — ADR 0024) and carries a SHA-256 digest of its own
canonical JSON so any later reader can prove the manifest unaltered.

What a pack does NOT claim: no external export happened (there is no SIEM
push, no S3 archive in this build — those zones stay flagged demonstration),
and the digest is an integrity fingerprint, not a PKI signature.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "PackNotFoundError",
    "create_pack",
    "get_pack",
    "load_packs",
    "verify_pack",
]

_MAX_PACKS: Final = 200


class PackNotFoundError(KeyError):
    """A pack id nobody ever created — said loudly, never an empty verdict."""


def _packs_path() -> Path:
    return get_settings().guard.audit_file.parent / "evidence_packs.json"


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def load_packs() -> list[dict[str, object]]:
    """Every created pack, oldest first (best-effort read)."""
    raw = _load_json(_packs_path(), [])
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def _digest(manifest: dict[str, object]) -> str:
    """SHA-256 over the manifest's canonical JSON (sorted keys, no digest field)."""
    canon = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _artifact_counts() -> dict[str, int]:
    """The REAL per-store artifact counts at this instant (imports deferred)."""
    from tessera.guard.ledger_store import verify_active_ledger
    from tessera.observability.eval.report_paths import iter_report_files
    from tessera.observability.replay import persisted_bundles
    from tessera.observability.spine.adapters import read_scores

    chain = verify_active_ledger()
    return {
        "audit_entries": chain.length,
        "eval_scores": len(read_scores(full=True)),
        "replay_bundles": len(persisted_bundles()),
        "eval_reports": sum(1 for _ in iter_report_files()),
    }


def create_pack(*, created_by: str) -> dict[str, object]:
    """Freeze a manifest of every durable proof store, attributed and digested.

    Args:
        created_by: The verified operator principal (``actor_of(session)``),
            never caller-supplied text and never a default.

    Returns:
        The stored pack: manifest fields + its ``sha256`` digest.
    """
    from tessera.guard.ledger_store import verify_active_ledger

    now = datetime.now(UTC)
    packs = load_packs()
    chain = verify_active_ledger()
    manifest: dict[str, object] = {
        "pack_id": f"PK-{now:%Y-%m-%d}-{len(packs) + 1:03d}",
        "created_at": now.isoformat(),
        "created_by": created_by,
        # The covered window: since the previous pack (or the chain's beginning).
        "period_start": str(packs[-1].get("created_at")) if packs else None,
        "period_end": now.isoformat(),
        "artifacts": _artifact_counts(),
        "chain": {
            "verified": chain.verified,
            "length": chain.length,
            "broken_at": chain.broken_at,
        },
    }
    pack: dict[str, object] = {**manifest, "sha256": _digest(manifest)}
    packs.append(pack)
    _save_json(_packs_path(), packs[-_MAX_PACKS:])
    return pack


def get_pack(pack_id: str) -> dict[str, object]:
    """Return one stored pack by id.

    Raises:
        PackNotFoundError: Unknown id.
    """
    for pack in load_packs():
        if pack.get("pack_id") == pack_id:
            return pack
    raise PackNotFoundError(pack_id)


def verify_pack(pack_id: str) -> dict[str, object]:
    """Re-derive the pack's digest and re-verify the live chain — a real verdict.

    Two independent facts, reported separately (never folded into one green):
    ``manifest_ok`` — the stored manifest re-derives to its stored digest, so
    nobody edited it; ``chain_verified_now`` — the live audit chain re-derives
    TODAY (which may differ from the verdict frozen inside the pack).

    Raises:
        PackNotFoundError: Unknown id.
    """
    from tessera.guard.ledger_store import verify_active_ledger

    pack = get_pack(pack_id)
    manifest = {k: v for k, v in pack.items() if k != "sha256"}
    chain_now = verify_active_ledger()
    return {
        "pack_id": pack_id,
        "manifest_ok": _digest(manifest) == pack.get("sha256"),
        "chain_verified_now": chain_now.verified,
        "chain_length_now": chain_now.length,
        "verified_at": datetime.now(UTC).isoformat(),
    }
