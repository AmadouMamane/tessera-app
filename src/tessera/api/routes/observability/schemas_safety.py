"""Wire contracts for the observability safety surface."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EmbeddingSpacePayload(BaseModel):
    """One embedding space observed in the stored corpus."""

    model_config = ConfigDict(extra="forbid")

    model: str
    dimension: int = Field(ge=1)
    rows: int = Field(ge=1)


class EmbeddingSkewPayload(BaseModel):
    """Evidence-backed compatibility verdict between query and corpus embeddings."""

    model_config = ConfigDict(extra="forbid")

    query_model: str
    query_dimension: int = Field(ge=1)
    corpus_model: str
    corpus_dimension: int = Field(ge=1)
    dimension_mismatch: bool
    model_mismatch: bool
    skew: bool
    severity: Literal["none", "soft", "hard", "unknown"]
    reason: str
    corpus_known: bool
    corpus_rows: int = Field(ge=0)
    unfingerprinted_rows: int = Field(ge=0)
    spaces: list[EmbeddingSpacePayload]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        """Reject internally contradictory evidence before it reaches the cockpit."""
        space_keys = [(space.model, space.dimension) for space in self.spaces]
        if len(space_keys) != len(set(space_keys)):
            msg = "embedding spaces must be unique by model and dimension"
            raise ValueError(msg)
        measured_rows = sum(space.rows for space in self.spaces)
        if measured_rows + self.unfingerprinted_rows != self.corpus_rows:
            msg = "embedding-space rows and unfingerprinted rows must cover the corpus exactly"
            raise ValueError(msg)
        if self.corpus_known and self.unfingerprinted_rows != 0:
            msg = "a fully known corpus cannot contain unfingerprinted rows"
            raise ValueError(msg)
        if self.severity == "none" and not self.corpus_known:
            msg = "an incompletely known corpus cannot receive a clean compatibility verdict"
            raise ValueError(msg)
        return self
