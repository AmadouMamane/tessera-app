"""Source document lookup endpoints for clickable chat citations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from tessera.corpus.sources import find_source_document
from tessera.settings import LanguageCode  # noqa: TCH001  FastAPI resolves it at runtime.

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceDocumentResponse(BaseModel):
    """User-visible source document backing a chat citation."""

    model_config = ConfigDict(extra="forbid")

    source: str
    locator: str
    language: LanguageCode
    corpus: str
    category: str
    text: str
    metadata: dict[str, str]


@router.get("/{source_path:path}")
async def get_source_document(
    source_path: str,
    language: Annotated[LanguageCode | None, Query()] = None,
) -> SourceDocumentResponse:
    """Return a packaged source document by canonical source id."""
    document = find_source_document(source_path, language=language)
    if document is None:
        raise HTTPException(status_code=404, detail="source not found")
    return SourceDocumentResponse(
        source=document.source,
        locator=document.locator,
        language=document.language,
        corpus=document.corpus,
        category=document.category,
        text=document.text,
        metadata=document.metadata,
    )
