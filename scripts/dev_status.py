"""`make dev-status` — ask the PROCESS what code it loaded. Never its directory.

The old version did this:

    pid=$(lsof …)  ·  cwd=$(lsof -d cwd $pid)  ·  head=$(git -C "$cwd" rev-parse HEAD)

and printed the answer in a column labelled `git`, which every reader — including its author —
took to mean *the code this server is serving*. It never was. It was the git head of a
**directory that happens to be the process's cwd**, and a directory is not a process. Move the
checkout under a live server and the witness reports the new sha with total composure.

That is not hypothetical. On 2026-07-13 the operator's backend had booted at 23:56 the previous
night — before the ledger fix landed — and `dev-status` printed the sha *of the fix*. His browser
paid 1 087 ms for a badge that costs 20 ms, and every witness on the machine said everything was
fine. **The witness was interrogating the neighbourhood of the truth instead of the truth**
(ADR 0026).

So now:

* the **process** is asked, over ``/healthz``, what it loaded — a content digest it captured at
  import and froze (:mod:`tessera.code_identity`), so a checkout moving underneath it cannot
  change what it reports;
* this script re-hashes the checkout **with the same function**, imported from the same module.
  One implementation, called from both sides of the comparison. A second copy of the digest,
  written in shell, would be a second thing to be wrong — and the two would drift the first time
  either was touched (the SQL-identifier lot already paid for that lesson once: two divergent
  private validators, and the hole survived in the gap between them);
* if the two digests differ, this server is not running the code in this checkout ⇒ **STALE**,
  loud, with the word *RESTART* in it. It does not speculate about *why* — the files may have
  changed under a live process, or the process may have been booted from another tree. The
  operator's question is the same in both cases, and so is the fix.

And when it **cannot** know — the server is down, or predates this witness and does not publish a
digest — it says so. It does not say ``ok``. A witness that cannot see must report a blind spot,
never a clean bill of health: that is the whole failure it was built to end.

The **frontend** row is deliberately different, and labelled as such. Its ``/api/healthz`` is a
*proxy* to the backend, so it cannot speak about itself; and it is served by ``next dev``, which
recompiles on change and therefore does not accumulate the staleness ``uvicorn`` does (booted
once, ``reload`` off, code loaded exactly once and never again). What is printed for it is the
**checkout**'s head, and the column says so.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tessera.code_identity import source_digest

_TIMEOUT_S: Final = 5.0
_SHORT: Final = 12


@dataclass(frozen=True, slots=True)
class Row:
    name: str
    port: str
    health_path: str
    #: Whether this server can speak about its own code. The frontend proxies; it cannot.
    speaks_for_itself: bool


def _listening_pid(port: str) -> str | None:
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    pid = out.stdout.strip().splitlines()
    return pid[0] if pid else None


def _process_cwd(pid: str) -> Path | None:
    try:
        out = subprocess.run(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        if line.startswith("n"):
            return Path(line[1:])
    return None


def _health(port: str, path: str) -> dict[str, Any] | None:
    """The process's own account of itself. ``None`` when it will not answer."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}{path}", timeout=_TIMEOUT_S
        ) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    return payload if isinstance(payload, dict) else None


def _checkout_head(directory: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "-"
    return out.stdout.strip() or "-"


def _verdict(health: dict[str, Any], cwd: Path | None) -> tuple[str, str]:
    """Does this process run the code in this checkout? Returns ``(loaded, verdict)``.

    The comparison is digest-to-digest: what the PROCESS says it loaded, against what the
    checkout holds RIGHT NOW. Note what it deliberately does **not** try to establish: *why* they
    differ. The files may have changed under a live server, or the server may have been booted
    from a different tree entirely. Both answer the operator's actual question the same way —
    *this server is not running the code in this checkout* — and both are fixed by the same
    action. A witness owes a true verdict, not a theory.
    """
    loaded_digest = health.get("code_digest")
    if not isinstance(loaded_digest, str) or not loaded_digest:
        # An older server, from before this witness existed. It cannot say what it loaded — and
        # this script must NOT fill that silence with a reassuring guess. A blind spot is reported
        # as a blind spot; that is the entire failure this lot exists to end.
        return "?", "⚠ CANNOT SAY (this server predates the code-identity witness) · RESTART"

    sha = health.get("code_sha")
    dirty = health.get("code_dirty")
    loaded = sha[:_SHORT] if isinstance(sha, str) and sha else f"digest:{loaded_digest[:8]}"
    if dirty is True:
        loaded += "+dirty"

    package = cwd / "src" / "tessera" if cwd else None
    if package is None or not package.is_dir():
        return loaded, "· cannot compare (no source tree at its working directory)"

    if source_digest(package) == loaded_digest:
        return loaded, "✓ it IS the code in this checkout"
    return loaded, "⚠ STALE — this server is NOT running the code in this checkout · RESTART"


def main() -> int:
    rows = (
        Row("frontend", sys.argv[1], "/api/healthz", speaks_for_itself=False),
        Row("backend", sys.argv[2], "/healthz", speaks_for_itself=True),
    )
    for row in rows:
        pid = _listening_pid(row.port)
        if pid is None:
            print(f"  {row.name:<8} :{row.port:<5} (not running)")
            continue

        health = _health(row.port, row.health_path)
        alive = "ok" if health is not None else "DOWN"

        if not row.speaks_for_itself:
            # It proxies /healthz to the backend, so its body describes the BACKEND, not itself.
            # Print the checkout it was started from, and LABEL it as the checkout — never as a
            # claim about the running code. `next dev` recompiles on change, so it does not go
            # stale the way uvicorn does (booted once, reload off).
            cwd = _process_cwd(pid)
            head = _checkout_head(cwd) if cwd else "-"
            print(
                f"  {row.name:<8} :{row.port:<5} pid {pid:<7} "
                f"checkout {head:<9} (next dev recompiles)   {alive}"
            )
            continue

        if health is None:
            print(
                f"  {row.name:<8} :{row.port:<5} pid {pid:<7} loaded ?"
                f"                     {alive}  ⚠ it will not say what it loaded"
            )
            continue

        loaded, verdict = _verdict(health, _process_cwd(pid))
        print(f"  {row.name:<8} :{row.port:<5} pid {pid:<7} loaded {loaded:<20} {alive}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
