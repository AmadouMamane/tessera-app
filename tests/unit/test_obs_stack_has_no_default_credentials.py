"""The plane that holds the transcripts had the weakest credentials in the repository.

`docker-compose.obs.claude.yml` brings up Langfuse, ClickHouse, MinIO, Redis and Grafana. **Langfuse
holds the LLM traces, and the LLM traces are customer conversations.** Until 2026-07-14 every one of
those credentials was a literal, readable on GitHub — `claude-demo-pw`, `miniosecret`,
`clickhouse/clickhouse`, and an `ENCRYPTION_KEY` of sixty-four ZEROS — and every port was published
as `"3900:3000"`, which Docker binds to **0.0.0.0, every interface**. On any shared network a
stranger could open Langfuse and read every transcript.

That is **F-9** — "default accounts stay valid when the env vars are missing" — closed in the app,
and left wide open in the plane that holds the transcripts. The question is never *"is this
production?"*; it is **"can a stranger reach it?"**, and the answer was yes, by default, today.

Worse than the passwords was the comment sitting on top of one: `${GF_ADMIN_PASSWORD:-changeme}`,
under the words *"No hardcoded credential in the repo"*. A false assurance is more dangerous than
the hole it denies, because it stops the next reader from looking.

So there is **no default credential anywhere**, and both witnesses are asserted here, because they
fail differently and a stranger only needs one gap:

* the **compose file itself** — `${VAR:?…}`, Compose's mandatory form. A stranger who runs
  `docker compose -f … up` directly, with no `make` in sight, is refused BY THE THING;
* the **`obs-guard` recipe** — so `make obs-up` refuses first, and says how to repair it.

A ratchet nobody has seen bite is not a ratchet. `TestTheGuardActuallyRefuses` takes the credentials
away and demands a named refusal with the exact remedy.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT: Final = Path(__file__).resolve().parents[2]
_COMPOSE: Final = _ROOT / "docker-compose.obs.claude.yml"
_MAKEFILE: Final = _ROOT / "Makefile"

#: What a credential looks like in a KEY. There is deliberately NO allow-list: a username is not a
#: credential, so `CLICKHOUSE_USER`, `MINIO_ROOT_USER` and `…_ACCESS_KEY_ID` do not match and need
#: no exemption — and a ratchet with an escape hatch polices nothing.
_CREDENTIAL_KEY: Final = re.compile(
    r"PASSWORD|SECRET|SALT|ENCRYPTION|BASIC_AUTH|REDIS_AUTH|REQUIREPASS|PUBLIC_KEY"
)

#: Compose's MANDATORY-variable form. Unset ⇒ Compose REFUSES TO START and names what is missing.
_MANDATORY: Final = re.compile(r"^\$\{[A-Z0-9_]+:\?[^}]*\}$")

#: Compose's DEFAULTED form. For a bind address that is fine — for a credential it IS the bug.
_DEFAULTED: Final = re.compile(r"\$\{(?P<var>[A-Z0-9_]+):-(?P<default>[^}]*)\}")

#: The published-port form we require: an explicit host IP, defaulting to loopback.
_BOUND_PORT: Final = re.compile(r"^\$\{TESSERA_OBS_BIND:-(?P<default>[^}]+)\}:\d+:\d+$")

#: Loopback, and nothing else, may be the DEFAULT bind. Reaching the stack from the network stays
#: possible — but only as a deliberate, declared act (`TESSERA_OBS_BIND=0.0.0.0`).
_LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "::1"})

#: Every credential that was live in this file on 2026-07-13. They may not come back — not here, not
#: as a "temporary" default, not in a comment that a copy-paste can revive.
_BANNED_LITERALS: Final = (
    "claude-demo-pw",
    "claude-nextauth-secret",
    "claude-powered-salt",
    "claude-redis",
    "miniosecret",
    "sk-lf-claude-secret",
    "pk-lf-claude-public",
    "changeme",
    "0000000000000000000000000000000000000000000000000000000000000000",
    # base64("pk-lf-claude-public:sk-lf-claude-secret") — the OTLP basic-auth header. The pragma is
    # detect-secrets' declared mechanism, and this is what it is for: a DEAD credential, written out
    # in full precisely so the ratchet can refuse it. Encoding it to dodge the scanner would hide it
    # from the next reader too, which is the one thing worse than the finding.
    "cGstbGYtY2xhdWRlLXB1YmxpYzpzay1sZi1jbGF1ZGUtc2VjcmV0",  # pragma: allowlist secret
)


def _document() -> dict[str, Any]:
    """The compose file as Compose reads it — merge keys resolved, anchors expanded."""
    loaded = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "the compose file no longer parses as a mapping"
    return loaded


def _scalars(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar in the document, with the dotted path that leads to it.

    The whole document, deliberately: a credential hides just as well in a `command:` or a
    `healthcheck:` as in an `environment:`, and `redis --requirepass` is exactly such a place.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _scalars(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _scalars(value, f"{path}[{index}]")
    else:
        yield path, node


def _tokens(value: str) -> set[str]:
    """A value split where a credential can actually END: whitespace, and URL/flag punctuation.

    `--requirepass claude-redis` yields the password; `tessera-claude-redis` does not. That is the
    whole difference between a witness and a grep.
    """
    return {token for token in re.split(r"[\s:/@\"'=,]+", value) if token}


def _obs_secrets_declared_in_the_makefile() -> set[str]:
    """The variables `obs-guard` demands. Parsed from the Makefile — never re-typed here."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^OBS_SECRETS\s*:?=(?P<body>(?:[^\n\\]*\\\n)*[^\n]*)$", text, re.MULTILINE)
    assert match is not None, "OBS_SECRETS is gone from the Makefile — the guard demands nothing."
    return set(re.findall(r"TESSERA_OBS_[A-Z0-9_]+", match.group("body")))


def _make_obs_guard(env_file: Path) -> subprocess.CompletedProcess[str]:
    """Run the REAL `obs-guard` recipe with every `TESSERA_OBS_*` stripped from the environment.

    Stripped, because the developer running this test may well have credentials exported — and a
    ratchet that passes because of the tester's own shell has tested the shell.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TESSERA_OBS_")}
    return subprocess.run(  # noqa: S603  literal argv, prints and exits — starts nothing
        ["make", "obs-guard", f"OBS_ENV_FILE={env_file}"],  # noqa: S607
        cwd=_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class TestNoCredentialHasADefault:
    """Every credential is mandatory, because a default that IS a credential is the bug."""

    def test_every_credential_key_is_a_mandatory_variable(self) -> None:
        offenders = [
            (path, value)
            for path, value in _scalars(_document())
            if _CREDENTIAL_KEY.search(path.rsplit(".", 1)[-1]) and not _MANDATORY.match(str(value))
        ]

        assert not offenders, (
            "a credential in the stack that holds the customer transcripts is not `${VAR:?…}`:\n"
            + "\n".join(f"  {path} = {value!r}" for path, value in offenders)
            + "\nCompose's mandatory form is the only one that REFUSES when the variable is unset. "
            "A literal, or a `${VAR:-default}`, means the stack boots for a stranger."
        )

    def test_no_credential_is_reachable_through_a_default(self) -> None:
        """`${GF_ADMIN_PASSWORD:-changeme}` — the exact line that carried "no hardcoded credential".

        Scanned over the WHOLE document, not just `environment:`: `${…:-…}` in a `command:` or a
        `healthcheck:` opens the stack just as wide.
        """
        offenders = [
            (path, match.group("var"), match.group("default"))
            for path, value in _scalars(_document())
            for match in _DEFAULTED.finditer(str(value))
            if _CREDENTIAL_KEY.search(match.group("var"))
        ]

        assert not offenders, (
            "a credential has a DEFAULT — so forgetting the variable is enough to open the stack:\n"
            + "\n".join(f"  {path}: ${{{var}:-{default}}}" for path, var, default in offenders)
        )

    def test_the_database_url_carries_no_inline_password(self) -> None:
        """A password hides in a URL's userinfo, where no key named `PASSWORD` ever appears."""
        offenders = [
            (path, value)
            for path, value in _scalars(_document())
            if isinstance(value, str)
            for match in [re.search(r"://[^:/@\s]+:(?P<secret>[^@\s]+)@", value)]
            if match and not _MANDATORY.match(match.group("secret"))
        ]

        assert not offenders, (
            "a connection string carries a literal password in its userinfo:\n"
            + "\n".join(f"  {path} = {value!r}" for path, value in offenders)
        )

    @pytest.mark.parametrize("literal", _BANNED_LITERALS)
    def test_the_literals_of_2026_07_13_never_come_back(self, literal: str) -> None:
        """The regression half — over the VALUES Compose reads, tokenised, which is the thing.

        Not a substring scan of the raw text. Written that way, this very test flared RED on
        `container_name: tessera-claude-redis`, because the dead Redis password was `claude-redis`
        — the `39b`-matched-as-`39` bug, reappearing inside the ratchet built to police it. A
        container name is not a credential, and saying so must not cost an exemption: tokenising
        the value separates them exactly, and leaves `--requirepass <literal>` still caught.
        """
        offenders = [
            (path, value) for path, value in _scalars(_document()) if literal in _tokens(str(value))
        ]

        assert not offenders, (
            f"{literal!r} is a LIVE value again in {_COMPOSE.name}:\n"
            + "\n".join(f"  {path} = {value!r}" for path, value in offenders)
            + "\nIt guarded the customer transcripts, in this file, until 2026-07-14 (F-9)."
        )

    def test_no_service_loads_credentials_from_a_committed_file(self) -> None:
        """The bypass this whole class would otherwise miss: `env_file: ./obs-defaults.env`.

        Every rule above reads the compose document. A service that pulls its credentials out of a
        SIDE file has no credential in the document at all — so every rule above goes green over a
        stack whose passwords are committed one directory away. There is no `env_file:` here today;
        adding one must cost a conversation, not a silent green.
        """
        offenders = [
            name
            for name, service in _document().get("services", {}).items()
            if "env_file" in service
        ]

        assert not offenders, (
            "a service declares `env_file:`, and every credential rule in this file reads the "
            "compose document only — so a committed env file walks straight past all of them:\n"
            + "\n".join(f"  {name}" for name in offenders)
        )

    def test_every_credential_compose_demands_is_a_credential_the_guard_demands(self) -> None:
        """The seam between the two witnesses. A gap here is a guard that greenlights a dead boot.

        Compose refusing at boot is still fail-closed, so this is not a security hole — it is an
        HONESTY hole: `obs-guard` would print nothing and `docker compose up` would then die on a
        variable the guard never mentioned. The remedy the guard names must be a remedy that works.
        """
        referenced = {
            var
            for _, value in _scalars(_document())
            for var in re.findall(r"\$\{(TESSERA_OBS_[A-Z0-9_]+):\?", str(value))
        }
        demanded = _obs_secrets_declared_in_the_makefile()

        assert referenced <= demanded, (
            "the compose file cannot start without these, and `obs-guard` never asks for them:\n"
            + "\n".join(f"  {var}" for var in sorted(referenced - demanded))
            + "\nAdd them to OBS_SECRETS (and to `make obs-secrets`), or the guard says OK and the "
            "stack then dies on a variable nobody named."
        )


class TestNothingIsPublishedToTheWholeNetworkByDefault:
    """`"3900:3000"` binds 0.0.0.0. The credential is the lock; the bind address is the door."""

    def test_every_published_port_binds_loopback_by_default(self) -> None:
        services = _document().get("services", {})
        offenders: list[tuple[str, str]] = []

        for name, service in services.items():
            for port in service.get("ports", []):
                match = _BOUND_PORT.match(str(port))
                if match is None or match.group("default") not in _LOOPBACK:
                    offenders.append((name, str(port)))

        assert not offenders, (
            'a port is published without an explicit loopback default — Docker binds `"3900:3000"`'
            " to 0.0.0.0, i.e. EVERY interface, so a stranger on the LAN reaches it:\n"
            + "\n".join(f"  {name}: {port!r}" for name, port in offenders)
            + '\nRequired: "${TESSERA_OBS_BIND:-127.0.0.1}:<host>:<container>".'
        )

    def test_at_least_one_port_is_published(self) -> None:
        """The control: a document with no `ports:` at all would pass the test above vacuously."""
        published = [
            port
            for service in _document().get("services", {}).values()
            for port in service.get("ports", [])
        ]

        assert published, "no published ports found — the test above is then asserting nothing."


class TestTheGuardCannotBeOrphanedOrSelfHealed:
    """A guard nobody runs is a decoration; a guard that repairs what it checks checks nothing."""

    @pytest.mark.parametrize("target", ["obs-up", "obs-up-core"])
    def test_the_up_targets_depend_on_the_guard(self, target: str) -> None:
        text = _MAKEFILE.read_text(encoding="utf-8")
        match = re.search(rf"^{re.escape(target)}:(?P<deps>[^\n]*)$", text, re.MULTILINE)

        assert match is not None, f"`{target}` is not a target in the Makefile any more."
        assert "obs-guard" in match.group("deps").split(), (
            f"`{target}` no longer runs `obs-guard`, so the stack that holds the customer "
            f"transcripts starts again without anyone asking for a password. Restore: "
            f"`{target}: obs-guard`."
        )

    def test_the_guard_does_not_generate_the_credentials_it_demands(self) -> None:
        """`obs-guard: obs-secrets` would mint the very credentials it exists to demand — F-14's
        shape exactly: a check that satisfies its own condition can never fail, and so checks
        nothing. The escape hatch stays a separate, deliberate command."""
        text = _MAKEFILE.read_text(encoding="utf-8")
        match = re.search(r"^obs-guard:(?P<deps>[^\n]*)$", text, re.MULTILINE)

        assert match is not None, "`obs-guard` is gone from the Makefile."
        assert "obs-secrets" not in match.group("deps"), (
            "`obs-guard` depends on `obs-secrets`: it now GENERATES the credentials it is supposed "
            "to demand, and can never refuse. That is F-14 — a witness that repairs its own "
            "condition reports 'ok' forever."
        )

    def test_the_generated_credentials_are_gitignored(self) -> None:
        """Asked of git, not the .gitignore text: that file is the neighbourhood, git the fact."""
        makefile = _MAKEFILE.read_text(encoding="utf-8")
        env_file = re.search(r"^OBS_ENV_FILE\s*:?=\s*(?P<path>\S+)$", makefile, re.MULTILINE)
        assert env_file is not None, "OBS_ENV_FILE is gone from the Makefile."

        result = subprocess.run(  # noqa: S603  literal argv
            ["git", "check-ignore", "-q", env_file.group("path")],  # noqa: S607
            cwd=_ROOT,
            check=False,
            capture_output=True,
        )

        assert result.returncode == 0, (
            f"`{env_file.group('path')}` is NOT gitignored — `make obs-secrets` would write twelve "
            f"live credentials into a tracked file."
        )


class TestTheGuardActuallyRefuses:
    """The mutation test. Take the credentials away and demand a named refusal with the remedy."""

    def test_with_no_credentials_it_refuses_and_names_the_remedy(self, tmp_path: Path) -> None:
        result = _make_obs_guard(tmp_path / "does-not-exist.env")
        out = result.stdout + result.stderr

        assert result.returncode == 2, (
            f"the stack has NO credentials and `make obs-guard` exited {result.returncode}. "
            f"`make obs-up` would then start Langfuse — and the transcripts with it.\n{out}"
        )
        assert "[NOT OK]" in out, f"it refused without publishing a verdict.\n{out}"
        assert "TESSERA_OBS_CLICKHOUSE_PASSWORD" in out, (
            f"it refused without naming what is missing. ClickHouse is where the transcripts are "
            f"STORED — if any variable deserves to be named, it is that one.\n{out}"
        )
        assert (
            "make obs-secrets" in out
        ), f"it named no repair. A red nobody can act on is a red people learn to ignore.\n{out}"
        assert "customer conversations" in out, (
            f"it refused without saying what is at stake. The reason this guard exists is not that "
            f"a password is missing — it is WHAT the password was guarding.\n{out}"
        )

    def test_with_every_credential_set_it_passes(self, tmp_path: Path) -> None:
        """The other half of the mutation. Without it, a guard that always refuses would pass above.

        The env file is written from the Makefile's OWN list, so the two cannot drift: add a
        credential to `OBS_SECRETS` and this half keeps testing the whole of it.
        """
        env_file = tmp_path / "obs.env"
        env_file.write_text(
            "".join(f"{var}=x\n" for var in sorted(_obs_secrets_declared_in_the_makefile())),
            encoding="utf-8",
        )

        result = _make_obs_guard(env_file)

        assert result.returncode == 0, (
            "every credential is set and the guard still refused — it would block every legitimate "
            "`make obs-up`, and a false red is the same disease as a false green.\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_one_missing_credential_is_enough_to_refuse(self, tmp_path: Path) -> None:
        """Eleven of twelve is not a lock. The guard must fail CLOSED on the twelfth."""
        demanded = sorted(_obs_secrets_declared_in_the_makefile())
        env_file = tmp_path / "obs.env"
        env_file.write_text(
            "".join(f"{var}=x\n" for var in demanded if var != "TESSERA_OBS_MINIO_PASSWORD"),
            encoding="utf-8",
        )

        result = _make_obs_guard(env_file)
        out = result.stdout + result.stderr

        assert result.returncode == 2, (
            f"eleven credentials of twelve, and the guard said OK. MinIO holds the uploaded trace "
            f"payloads.\n{out}"
        )
        assert "TESSERA_OBS_MINIO_PASSWORD" in out, f"it refused without naming the one gap.\n{out}"


def _recipe(target: str) -> str:
    """The body of a Makefile target — the lines make would actually run, nothing else."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(target)}:[^\n]*\n(?P<body>(?:\t[^\n]*\n)*)", text, re.MULTILINE
    )
    assert match is not None, f"`{target}` is not a target in the Makefile any more."
    return match.group("body")


def _commands_of(body: str) -> str:
    """A recipe with everything it merely PRINTS removed — what it runs, not what it says.

    A refusal is required to name its own repair, so the word appears in an `echo`. Only the
    difference between naming and invoking makes the wiring assertion mean anything.
    """
    return "\n".join(re.sub(r"\b(echo|printf)\b.*", "", line) for line in body.splitlines())


class TestASetCredentialIsNotAnAcceptedCredential:
    """`obs-guard` asks whether a credential is SET. Nothing asked whether it was ACCEPTED.

    On 2026-08-04 `tessera-claude-langfuse` had restarted **818 times** against
    `P1000 Authentication failed`, for fourteen hours, while every witness in this repository was
    green: the variable *was* set, so `obs-guard` passed. Postgres and ClickHouse bake their
    password when the VOLUME IS INITIALISED and ignore the env for ever after, so regenerating
    `.env.obs.local` — or keeping a volume older than it — diverges the two in silence.

    The trap that hid it for a whole morning is worth its own assertion below: `docker exec …
    psql -U langfuse` SUCCEEDS with the wrong password, because the image's local socket is
    `trust`. A probe that takes that path certifies a credential nobody can use.
    """

    def test_the_up_target_verifies_and_not_only_guards(self) -> None:
        body = _recipe("obs-up")

        assert "obs-verify" in body, (
            "`make obs-up` starts the stack and never asks whether the stores accept the "
            "credentials it just handed them. That is how 818 crash-loops went unremarked for "
            "fourteen hours. Restore the `obs-verify` step."
        )

    def test_the_probe_does_not_take_the_trust_socket(self) -> None:
        """`docker exec … psql` authenticates over the local socket, which the postgres image
        trusts unconditionally. A witness that asks the question that way cannot fail, and so is
        not a witness — ADR 0026, and the exact reason this bug survived a morning of looking."""
        body = _recipe("obs-verify")

        assert "docker exec" not in body, (
            "`obs-verify` probes with `docker exec`, i.e. over the container's LOCAL socket — "
            "which `pg_hba.conf` sets to `trust`, so it succeeds with ANY password. It would "
            "certify exactly the credential that crash-looped Langfuse. Probe over TCP, from "
            "`--network`, the way Langfuse itself connects."
        )
        assert "--network" in body, (
            "`obs-verify` no longer probes from the stack's own network, so it is no longer "
            "taking the path the application takes."
        )

    def test_the_verifier_does_not_repair_what_it_checks(self) -> None:
        """The same law that forbids `obs-guard: obs-secrets`. A check that satisfies its own
        condition can never fail, and so has checked nothing."""
        text = _MAKEFILE.read_text(encoding="utf-8")
        deps = re.search(r"^obs-verify:(?P<deps>[^\n]*)$", text, re.MULTILINE)
        assert deps is not None, "`obs-verify` is gone from the Makefile."

        assert "obs-realign" not in deps.group("deps"), (
            "`obs-verify` depends on `obs-realign`: it now REPAIRS the divergence it exists to "
            "report, and can never be red. The repair stays a separate, deliberate command."
        )
        assert "ALTER USER" not in _recipe("obs-verify"), (
            "`obs-verify` rewrites the stored password itself. A store that silently realigns to "
            "whatever the caller brought is not a store whose credential means anything."
        )

    def test_the_refusal_names_the_repair(self) -> None:
        """A red nobody can act on is a red people learn to ignore."""
        body = _recipe("obs-verify")

        assert "obs-realign" in body, (
            "`obs-verify` refuses without naming `make obs-realign`, the one command that fixes "
            "it. The operator is left with `P1000` and a guess."
        )

    def test_the_repair_is_not_wired_into_anything(self) -> None:
        """Nothing may run `obs-realign` on its own: it mutates a stored credential.

        NAMING it is required — the refusal above must say how to repair itself — so the whole
        assertion is the difference between a recipe that PRINTS the word and one that RUNS the
        command. Printed text is dropped before looking.
        """
        text = _MAKEFILE.read_text(encoding="utf-8")
        callers = [
            target
            for target in re.findall(r"^([a-z][a-z0-9-]*):[^\n=]*$", text, re.MULTILINE)
            if target != "obs-realign" and "obs-realign" in _commands_of(_recipe(target))
        ]

        assert callers == [], (
            f"{callers} run `obs-realign` automatically. Rewriting a database password must stay "
            f"an act somebody chose, not a side effect of starting a stack."
        )
