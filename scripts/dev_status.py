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

.. rubric:: 2026-07-13, the fifth instance — and it was in here

All of the above was true of what this script **printed**, and false of what it **returned**.
``main()`` ended in ``return 0``, unconditionally. It printed ``⚠ STALE — this server is NOT
running the code in this checkout · RESTART``, and it printed ``⚠ CANNOT SAY (this server predates
the code-identity witness)``, and then it told its caller, in the only language a caller reads,
**ok**. ``make dev-status`` was green on every one of its own failure verdicts.

The doctrine had been implemented in the *rendering* and forgotten in the *exit code* — which is to
say, forgotten on **the exact surface it was born on**: the origin instance of ADR 0026 is an empty
``${PIPESTATUS[0]}`` that manufactured a green. A verdict a human must read to act on is not a
verdict a machine can act on, and this repo's own rule — *a witness that cannot see may never
report "ok"* — does not have an exception for the shell.

So the exit code is now the verdict (:mod:`tessera.verdict`): ``0`` iff the servers we can ask are
running the code in this checkout; ``2`` for STALE and for every blind spot alike, because to a
caller they mean the same thing — *do not proceed on my say-so*.

The **frontend** row is deliberately different, and labelled as such. Its ``/api/healthz`` is a
*proxy* to the backend, so it cannot speak about itself; and it is served by ``next dev``, which
recompiles on change and therefore does not accumulate the staleness ``uvicorn`` does (booted
once, ``reload`` off, code loaded exactly once and never again). What is printed for it is the
**checkout**'s head, and the column says so — it is a report, and it is not voted on.
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
from tessera.verdict import CannotSay, NotOk, Ok, Verdict, exit_code, render

_TIMEOUT_S: Final = 5.0
_SHORT: Final = 12


@dataclass(frozen=True, slots=True)
class Row:
    name: str
    port: str
    health_path: str
    #: Whether this server can speak about its own code. The frontend proxies; it cannot.
    speaks_for_itself: bool


@dataclass(frozen=True, slots=True)
class Listening:
    """What is on the port. ``pid=None`` means **nothing is** — an observation, not a failure."""

    pid: str | None


def _listening_pid(port: str) -> Listening | CannotSay:
    """Who listens on ``port``? Three answers, and the third one used to be missing.

    ``lsof`` refusing to run (absent, sandboxed, out of file descriptors) and ``lsof`` returning
    nothing are **different facts**, and this function used to collapse both into ``None`` — which
    the caller then printed as ``(not running)``. A machine that could not be asked was reported as
    a machine that is not there. That is the shape of every incident in ADR 0026, in four lines.
    """
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-tiTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CannotSay(f"cannot ask which process listens on :{port} — `lsof` did not run: {exc}")
    # lsof exits 1 when nothing matches. That is not an error, it is the answer "nobody".
    if out.returncode > 1:
        return CannotSay(
            f"cannot ask which process listens on :{port} — `lsof` exited {out.returncode}: "
            f"{out.stderr.strip() or '(no message)'}"
        )
    pid = out.stdout.strip().splitlines()
    return Listening(pid=pid[0] if pid else None)


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


def _verdict(health: dict[str, Any], cwd: Path | None) -> tuple[str, Verdict]:
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
        return "?", CannotSay(
            "this server predates the code-identity witness and will not say what it loaded "
            "· RESTART it and the question becomes answerable"
        )

    sha = health.get("code_sha")
    dirty = health.get("code_dirty")
    loaded = sha[:_SHORT] if isinstance(sha, str) and sha else f"digest:{loaded_digest[:8]}"
    if dirty is True:
        loaded += "+dirty"

    package = cwd / "src" / "tessera" if cwd else None
    if package is None or not package.is_dir():
        return loaded, CannotSay(
            "cannot compare: there is no source tree at this process's working directory, so "
            "there is nothing to hash it against"
        )

    if source_digest(package) == loaded_digest:
        return loaded, Ok(f"it IS the code in this checkout (digest {loaded_digest[:_SHORT]})")
    return loaded, NotOk(
        "STALE — this server is NOT running the code in this checkout · RESTART "
        f"(it loaded {loaded_digest[:_SHORT]}, the checkout is {source_digest(package)[:_SHORT]})"
    )


def _mark(verdict: Verdict) -> str:
    """The tick or the warning, for the human reading the row. ``Ok`` — and only ``Ok`` — is ✓."""
    return "✓" if isinstance(verdict, Ok) else "⚠"


def _row_verdict(row: Row) -> Verdict:
    """One server, one verdict — and the row printed on the way."""
    listening = _listening_pid(row.port)
    if isinstance(listening, CannotSay):
        print(f"  {row.name:<8} :{row.port:<5} ⚠ {listening.blind_spot}")
        return listening

    if listening.pid is None:
        # We looked, with a working `lsof`, and nothing is there. That is a FACT, not a hole: a
        # server that is not running cannot be stale. Reporting it as a failure would be a false
        # red, and a false red trains you to ignore reds.
        print(f"  {row.name:<8} :{row.port:<5} (not running)")
        return Ok(f"{row.name} is not running on :{row.port} — nothing to be stale")

    pid = listening.pid
    health = _health(row.port, row.health_path)
    alive = "ok" if health is not None else "DOWN"

    if not row.speaks_for_itself:
        # It proxies /healthz to the backend, so its body describes the BACKEND, not itself.
        # Print the checkout it was started from, and LABEL it as the checkout — never as a
        # claim about the running code. `next dev` recompiles on change, so it does not go
        # stale the way uvicorn does (booted once, reload off). This row is a REPORT: it makes
        # no claim, so it casts no vote.
        cwd = _process_cwd(pid)
        head = _checkout_head(cwd) if cwd else "-"
        print(
            f"  {row.name:<8} :{row.port:<5} pid {pid:<7} "
            f"checkout {head:<9} (next dev recompiles)   {alive}"
        )
        return Ok(f"{row.name} on :{row.port} is a proxy — it makes no claim about its own code")

    if health is None:
        print(
            f"  {row.name:<8} :{row.port:<5} pid {pid:<7} loaded ?"
            f"                     {alive}  ⚠ it will not say what it loaded"
        )
        return CannotSay(
            f"{row.name} on :{row.port} (pid {pid}) is listening but will not answer "
            f"{row.health_path} — it cannot be asked what it loaded"
        )

    loaded, verdict = _verdict(health, _process_cwd(pid))
    detail = render(verdict).split("] ", 1)[-1]
    print(
        f"  {row.name:<8} :{row.port:<5} pid {pid:<7} loaded {loaded:<20} "
        f"{alive}  {_mark(verdict)} {detail}"
    )
    return verdict


def _worst(verdicts: list[Verdict]) -> Verdict:
    """The verdict the process publishes: the worst one, never the most convenient one.

    A ``NotOk`` outranks a ``CannotSay`` outranks an ``Ok`` — and note there is no reduction here
    that could produce an ``Ok`` out of anything else, because :class:`Ok` cannot be constructed
    without evidence and there is none to give.
    """
    for verdict in verdicts:
        if isinstance(verdict, NotOk):
            return verdict
    for verdict in verdicts:
        if isinstance(verdict, CannotSay):
            return verdict
    return Ok("; ".join(v.evidence for v in verdicts if isinstance(v, Ok)) or "nothing to report")


def main() -> int:
    """Exit code IS the verdict. ``0`` only when every server we could ask is current.

    This line used to be ``return 0``. It printed STALE and it printed CANNOT SAY, and it returned
    zero for both — the witness of ADR 0026, reporting "ok" on its own blind spot, in the one
    channel its caller actually reads.
    """
    rows = (
        Row("frontend", sys.argv[1], "/api/healthz", speaks_for_itself=False),
        Row("backend", sys.argv[2], "/healthz", speaks_for_itself=True),
    )
    verdict = _worst([_row_verdict(row) for row in rows])

    stream = sys.stdout if isinstance(verdict, Ok) else sys.stderr
    stream.write(f"\n[dev-status] {render(verdict)}\n")
    stream.flush()
    return exit_code(verdict)


if __name__ == "__main__":
    raise SystemExit(main())
