"""Every datastore port in every compose file of this repository binds loopback by default.

On 2026-07-15 the PRODUCT database was readable from the LAN. `tessera-postgres` — the audit
ledger, the conversation transcripts, the GDPR long-term memory — answered on `0.0.0.0:5432`,
`tessera-redis` on `0.0.0.0:6379`, with credentials published in this very repository
(`tessera`/`tessera`). The macOS application firewall does not police Docker's port publishing,
so "bound to every interface" means exactly what it says: any host on the network segment.

That is **F-9** — "default accounts stay valid, and the door is open by default" — for the third
time, one file over each time. The app closed it (`webapp/frontend/lib/auth/`); the obs stack
closed it on 2026-07-14 (`docker-compose.obs.claude.yml`, `${TESSERA_OBS_BIND:-127.0.0.1}` on
every port); and the base `docker-compose.yml` still published a bare `"5432:5432"`, because the
obs fix lived in ONE file and its witness (`test_obs_stack_has_no_default_credentials.py`) reads
ONE file. A correction whose witness stops at the file it was written for is re-opened by the
next compose file somebody adds.

So this ratchet reads the REPOSITORY, not a file:

* **every** `docker-compose*.yml`, wherever it lives — including the obs stack, so the 2026-07-14
  correction and this one are policed by the SAME witness and cannot diverge;
* every service whose image is a **datastore** (that is where the customer data sits; an nginx
  gateway's PURPOSE is to be reached — ADR 0020 — so app/edge services are out of scope, and
  saying so here is what keeps the scope honest);
* every published port must carry a **statically resolvable loopback default** — `127.0.0.1`,
  `::1` or `localhost`, either literal or as `${VAR:-127.0.0.1}`. Publishing to the network stays
  possible, but only as a deliberate, declared act (`TESSERA_BIND=0.0.0.0`), never as what you
  get by forgetting. The resolution is static ON PURPOSE: the verdict is about the FILE's default
  posture, so an exported `TESSERA_BIND=0.0.0.0` in the tester's own shell must not flip it.

And because a witness that cannot see may never report "ok" (ADR 0026): a port entry this parser
does not understand, or a YAML tag it does not know, is a RED, not a skip.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

_ROOT: Final = Path(__file__).resolve().parents[2]

#: Directories that hold other people's code or build output — not this repository's compose files.
_FOREIGN_PARTS: Final = frozenset({".git", ".venv", "node_modules", ".next", ".pytest_cache"})

#: The compose files this ratchet exists for. The glob may FIND MORE (that is the point — a new
#: compose file is policed the day it is added); it may never find fewer. A discovery that cannot
#: see the file this lot fixed is asserting nothing.
_EXPECTED_FILES: Final = frozenset(
    {
        "docker-compose.yml",
        "docker-compose.unix.yml",
        "docker-compose.obs.claude.yml",
        "infra/edge/docker-compose.gateway.yml",
    }
)

#: What a datastore looks like in an `image:`. Substring match over the full image reference,
#: deliberately: `pgvector/pgvector:pg16`, `clickhouse/clickhouse-server:24.8` and a `postgres:16`
#: named `langfuse-db` must all match, and a false positive is a conversation, not a hole.
_DATASTORE_IMAGE_TOKENS: Final = frozenset(
    {
        "postgres",
        "pgvector",
        "redis",
        "valkey",
        "clickhouse",
        "minio",
        "mysql",
        "mariadb",
        "mongo",
        "elasticsearch",
        "opensearch",
        "cassandra",
        "memcached",
        "neo4j",
        "etcd",
    }
)

#: Loopback, and nothing else, may be the default bind.
_LOOPBACK: Final = frozenset({"127.0.0.1", "::1", "localhost"})

#: Compose's defaulted-variable forms, `${VAR:-default}` and `${VAR-default}`. These are the ONLY
#: interpolations resolved: the ratchet judges the file's own default posture, never the shell's.
_DEFAULTED: Final = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:?-(?P<default>[^}]*)\}")

#: Known holes, FROZEN, keyed `<file> :: services.<name> :: <entry>`. This set may only SHRINK:
#: fixing a hole deletes its line (and `test_the_freeze_carries_no_dead_entries` forces the
#: deletion); adding one is the red this ratchet exists to raise. It is empty because the lot that
#: wrote this file closed every hole it found — keep it that way.
_FROZEN_EXCEPTIONS: Final[frozenset[str]] = frozenset()


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands Compose's two documented override tags, and nothing more.

    `!reset` and `!override` are real Compose semantics (the edge gateway uses `ports: !reset []`)
    and hide no address, so they load as their plain value. Any OTHER tag is semantics this
    witness does not model — loading raises, the test goes red, and the tag earns its constructor
    in review instead of being skipped over in silence.
    """


def _construct_tagged(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    """Load a `!reset`/`!override`-tagged node as the plain value it decorates."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    raise yaml.constructor.ConstructorError(  # pragma: no cover — yaml has no fourth node kind
        None, None, f"unexpected node kind under {node.tag}", node.start_mark
    )


for _tag in ("!reset", "!override"):
    _ComposeLoader.add_constructor(_tag, _construct_tagged)


def _compose_files() -> list[Path]:
    """Every docker-compose*.yml/.yaml in the repository, wherever it lives."""
    return sorted(
        path
        for pattern in ("docker-compose*.yml", "docker-compose*.yaml")
        for path in _ROOT.rglob(pattern)
        if not _FOREIGN_PARTS.intersection(path.relative_to(_ROOT).parts)
    )


def _load(text: str) -> dict[str, Any]:
    """Parse one compose document; anything but a mapping at the top is a red, not a skip."""
    loaded = yaml.load(text, Loader=_ComposeLoader)  # noqa: S506 — a SafeLoader subclass
    if not isinstance(loaded, dict):
        raise TypeError(f"compose document is {type(loaded).__name__}, not a mapping")
    return loaded


def _resolve_static_defaults(value: str) -> str:
    """`${VAR:-default}` becomes `default`; every other `${…}` form is left in place.

    Left in place, deliberately: `${VAR}` and `${VAR:?msg}` have NO static default, so whatever
    posture the file has then depends on the invoker's shell — which is exactly the "unknowable
    by reading the file" condition `_port_violation` refuses.
    """
    return _DEFAULTED.sub(lambda match: match.group("default"), value)


def _is_datastore(service: dict[str, Any]) -> bool:
    """Whether a service's image names a datastore. Build-only services are this repo's own app."""
    image = str(service.get("image", "")).lower()
    return any(token in image for token in _DATASTORE_IMAGE_TOKENS)


def _long_syntax_violation(entry: dict[str, Any]) -> str | None:
    """The long-syntax half of `_port_violation`: the address lives under `host_ip`."""
    host_ip = entry.get("host_ip")
    if host_ip is None:
        return "long-syntax mapping without host_ip — Docker publishes it on every interface"
    resolved = _resolve_static_defaults(str(host_ip))
    if "$" in resolved:
        return f"host_ip {host_ip!r} has no static default — the file's posture is unknowable"
    if resolved not in _LOOPBACK:
        return f"host_ip defaults to {resolved!r}, not loopback"
    return None


def _port_violation(entry: object) -> str | None:
    """Why one published-port entry does not bind loopback by default — None when it does."""
    if isinstance(entry, dict):
        return _long_syntax_violation(entry)

    text = _resolve_static_defaults(str(entry))
    if "$" in text:
        return f"{entry!r} has no static default — the file's posture depends on the shell"
    if text.startswith("["):
        closing = text.find("]")
        if closing == -1:
            return f"unparseable port entry {entry!r} — a witness that cannot see never says ok"
        address = text[1:closing]
    else:
        without_container = text.rpartition(":")[0]
        address, colon, _host_port = without_container.rpartition(":")
        if not colon:
            return (
                'no host address — a bare "5432:5432" (or a lone container port) is what Docker '
                "binds to 0.0.0.0, i.e. EVERY interface"
            )
    if address not in _LOOPBACK:
        return f"binds {address!r} by default, not loopback"
    return None


def _document_violations(document: dict[str, Any], origin: str) -> list[tuple[str, str]]:
    """`(key, why)` for every datastore port in one compose document that reaches past loopback."""
    services = document.get("services") or {}
    if not isinstance(services, dict):
        raise TypeError(f"{origin}: `services` is {type(services).__name__}, not a mapping")
    return [
        (f"{origin} :: services.{name} :: {entry!r}", why)
        for name, service in services.items()
        if isinstance(service, dict) and _is_datastore(service)
        for entry in service.get("ports") or []
        for why in [_port_violation(entry)]
        if why is not None
    ]


def _datastore_port_count(document: dict[str, Any]) -> int:
    """How many published datastore ports one document carries — the anti-vacuity measure."""
    return sum(
        len(service.get("ports") or [])
        for service in (document.get("services") or {}).values()
        if isinstance(service, dict) and _is_datastore(service)
    )


def _repo_documents() -> dict[str, dict[str, Any]]:
    """Every compose document in the repository, keyed by its path relative to the root."""
    return {
        str(path.relative_to(_ROOT)): _load(path.read_text(encoding="utf-8"))
        for path in _compose_files()
    }


class TestEveryDatastorePortBindsLoopbackByDefault:
    """The ratchet — over the repository, so the next compose file is born policed."""

    def test_no_datastore_port_reaches_past_loopback(self) -> None:
        offenders = [
            (key, why)
            for origin, document in _repo_documents().items()
            for key, why in _document_violations(document, origin)
            if key not in _FROZEN_EXCEPTIONS
        ]

        assert not offenders, (
            "a datastore port reaches past loopback by default — on 2026-07-15 this exact hole "
            "had the audit ledger, the transcripts and the GDPR memory answering the LAN:\n"
            + "\n".join(f"  {key}\n    — {why}" for key, why in offenders)
            + '\nRequired: "${TESSERA_BIND:-127.0.0.1}:<host>:<container>" (loopback default, '
            "publishing is a declared act), and NOT a new entry in _FROZEN_EXCEPTIONS — that "
            "list only shrinks."
        )

    def test_the_freeze_carries_no_dead_entries(self) -> None:
        """A frozen exception whose hole is closed must be deleted — the ratchet only goes down."""
        live = {
            key
            for origin, document in _repo_documents().items()
            for key, _ in _document_violations(document, origin)
        }
        dead = _FROZEN_EXCEPTIONS - live

        assert not dead, (
            "these frozen exceptions no longer match a live violation — delete them, so the "
            "freeze keeps counting only what is real:\n" + "\n".join(f"  {key}" for key in dead)
        )

    def test_the_discovery_sees_the_files_it_polices(self) -> None:
        """The glob may find MORE files than this list; it may never find fewer."""
        found = {str(path.relative_to(_ROOT)) for path in _compose_files()}
        missing = _EXPECTED_FILES - found

        assert not missing, (
            "compose files this ratchet exists for are invisible to its discovery — every verdict "
            "above is then about a repository that is not this one:\n"
            + "\n".join(f"  {name}" for name in sorted(missing))
        )

    def test_the_obs_stack_is_policed_by_this_same_ratchet(self) -> None:
        """The 2026-07-14 obs fix and this lot must be one witness, or they diverge (lot §3)."""
        documents = _repo_documents()
        assert _datastore_port_count(documents["docker-compose.obs.claude.yml"]) >= 4, (
            "the obs stack no longer contributes datastore ports to this ratchet — its loopback "
            "correction is then policed by nothing repo-wide, and the two fixes drift apart."
        )

    def test_the_base_stack_is_policed(self) -> None:
        """The anti-vacuity control: the very stack this lot fixed must be measured by it."""
        documents = _repo_documents()
        assert _datastore_port_count(documents["docker-compose.yml"]) >= 1, (
            "docker-compose.yml no longer contributes a datastore port — the test above would "
            "then be green over the exact file this ratchet was written for."
        )


class TestTheCheckerActuallyBites:
    """The mutation half, on synthetic documents THROUGH THE REAL COLLECTION PATH.

    A ratchet nobody has seen bite is not a ratchet: each shape that ever carried this hole is
    fed to the same `_document_violations` the repository scan uses, and must come back named.
    """

    @pytest.mark.parametrize(
        "entry",
        [
            "5432:5432",  # the exact line tessera-postgres leaked through
            "0.0.0.0:5432:5432",
            "6379",  # lone container port — ephemeral host port, still 0.0.0.0
            5432,  # YAML unquoted scalar arrives as an int
            "${TESSERA_BIND:-0.0.0.0}:5432:5432",  # a default that is the bug
            "${TESSERA_BIND}:5432:5432",  # no static default — shell decides
            "${TESSERA_BIND:?set it}:5432:5432",  # mandatory form: still no static default
            "192.168.1.19:5432:5432",
            {"target": 5432, "published": 5432},  # long syntax, no host_ip
            {"target": 5432, "published": 5432, "host_ip": "0.0.0.0"},  # noqa: S104 — the input under test
        ],
    )
    def test_every_leaking_shape_is_refused(self, entry: object) -> None:
        assert _port_violation(entry) is not None, f"{entry!r} reaches past loopback and passed"

    @pytest.mark.parametrize(
        "entry",
        [
            "127.0.0.1:5432:5432",
            "${TESSERA_BIND:-127.0.0.1}:${TESSERA_PG_PORT:-5432}:5432",  # the fixed line
            "${TESSERA_OBS_BIND:-127.0.0.1}:16379:6379",  # the obs stack's form
            "[::1]:6379:6379",
            "localhost:5432:5432",
            {"target": 5432, "published": 5432, "host_ip": "127.0.0.1"},
        ],
    )
    def test_every_loopback_shape_passes(self, entry: object) -> None:
        assert _port_violation(entry) is None, f"{entry!r} is loopback-by-default and was refused"

    def test_a_leak_in_a_document_is_named_through_the_real_path(self) -> None:
        document = _load(
            "services:\n  db:\n    image: postgres:16\n    ports:\n      - '5432:5432'\n"
        )
        violations = _document_violations(document, "synthetic.yml")

        assert [key for key, _ in violations] == ["synthetic.yml :: services.db :: '5432:5432'"]

    def test_a_non_datastore_service_is_out_of_scope(self) -> None:
        """Scope honesty: the edge gateway's PURPOSE is to be reached (ADR 0020)."""
        document = _load(
            "services:\n  gateway:\n    image: nginx:1.27-alpine\n    ports:\n      - '443:443'\n"
        )

        assert _document_violations(document, "synthetic.yml") == []

    def test_compose_override_tags_load_as_their_plain_value(self) -> None:
        document = _load("services:\n  agent:\n    ports: !reset []\n")

        assert document["services"]["agent"]["ports"] == []

    def test_an_unknown_tag_is_a_red_not_a_skip(self) -> None:
        with pytest.raises(yaml.YAMLError):
            _load("services:\n  db:\n    image: postgres:16\n    ports: !mystery []\n")

    def test_a_non_mapping_document_is_a_red_not_a_skip(self) -> None:
        with pytest.raises(TypeError):
            _load("- not\n- a\n- compose file\n")
