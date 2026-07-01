"""The first-class ``Scope`` value object (ADR 0015).

Scope is parsed once and generalises ADR 0011's as-of-T into one dimension. These tests
lock its parsing, the active-filter set, the dimension narrowing (which is what makes a
"filter shown but ignored" state unrepresentable), and the label/key serialisations.
"""

from __future__ import annotations

from tessera.observability.spine.scope import Dimension, Scope


class TestFromQuery:
    def test_agent_all_and_blank_map_to_org(self) -> None:
        assert Scope.from_query({"agent": "all"}).agent_id is None
        assert Scope.from_query({"agent": ""}).agent_id is None
        assert Scope.from_query({"agent": "  "}).agent_id is None
        assert Scope.from_query({}).agent_id is None

    def test_concrete_agent_and_instant(self) -> None:
        scope = Scope.from_query({"agent": "support-client", "at": "2026-06-12T10:00:00Z"})
        assert scope.agent_id == "support-client"
        assert scope.at == "2026-06-12T10:00:00Z"
        assert scope.agent_param == "support-client"

    def test_agent_param_round_trips_org(self) -> None:
        assert Scope().agent_param == "all"
        assert Scope(agent_id="x").agent_param == "x"

    def test_optional_dimensions(self) -> None:
        scope = Scope.from_query({"language": "fr", "model": "llama3.2:3b"})
        assert scope.language == "fr"
        assert scope.model == "llama3.2:3b"
        assert scope.environment is None


class TestFilters:
    def test_empty_scope_has_no_filters(self) -> None:
        assert Scope().filters == frozenset()

    def test_active_filters_reflect_set_dimensions(self) -> None:
        scope = Scope(at="2026-06-12T10:00:00Z", agent_id="support", language="fr")
        assert scope.filters == frozenset({Dimension.TIME, Dimension.AGENT, Dimension.LANGUAGE})


class TestNarrowTo:
    def test_drops_unsupported_dimensions(self) -> None:
        scope = Scope(at="2026-06-12T10:00:00Z", agent_id="support", language="fr")
        # An org-wide, time-only signal keeps only TIME — agent + language cannot leak in.
        narrowed = scope.narrow_to(frozenset({Dimension.TIME}))
        assert narrowed.at == scope.at
        assert narrowed.agent_id is None
        assert narrowed.language is None

    def test_keeps_supported_dimensions(self) -> None:
        scope = Scope(at="2026-06-12T10:00:00Z", agent_id="support")
        narrowed = scope.narrow_to(frozenset({Dimension.AGENT, Dimension.TIME}))
        assert narrowed == scope

    def test_narrowing_to_empty_yields_org_live(self) -> None:
        scope = Scope(at="2026-06-12T10:00:00Z", agent_id="support")
        narrowed = scope.narrow_to(frozenset())
        assert narrowed == Scope()


class TestSerialisation:
    def test_to_labels_omits_time_and_none(self) -> None:
        scope = Scope(at="2026-06-12T10:00:00Z", agent_id="support", language="fr")
        labels = scope.to_labels()
        assert labels == {"agent_id": "support", "language": "fr"}
        assert "at" not in labels  # the temporal bound is a range, not a label

    def test_key_is_stable_and_distinguishes_scopes(self) -> None:
        a = Scope(agent_id="support").key()
        b = Scope(agent_id="support").key()
        c = Scope(agent_id="recouvrement").key()
        assert a == b
        assert a != c
        assert Scope().key() != Scope(at="2026-06-12T10:00:00Z").key()
