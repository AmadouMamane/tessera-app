"""Generate real knowledge traffic: which questions are grounded on which source.

Runs a set of realistic EU retail-banking questions (the kind Tessera answers)
through the live retrieval store and records, per knowledge source, the questions
that retrieved it above a similarity threshold, plus the moment. The result is
cached to ``<guard.audit_file.parent>/knowledge_traffic.json`` and consumed by
:mod:`tessera.observability.knowledge` to fill the "Reponses ancrees" tab and the
"Derniere utilisation" usage figure with real data.

Run::

    PYTHONPATH=.:src .venv/bin/python -m scripts.generate_traffic
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from tessera.observability.knowledge import _SOURCE_META, _state_path
from tessera.retrieval.embeddings import embed
from tessera.retrieval.store import knn_search

_CORPORA = ("regulations", "credit_aurore")
_TOP_K = 5
_THRESHOLD = 0.55

# Realistic banking questions (fr/de/en), in the spirit of Tessera's use case.
_QUESTIONS: list[str] = [
    "Comment ouvrir un compte courant chez Credit Aurore ?",
    "Quels sont les frais de la carte Visa Premier ?",
    "Que faire en cas de perte ou de vol de ma carte bancaire ?",
    "Comment exercer mon droit d'acces a mes donnees aupres de la banque ?",
    "Quelles sont les conditions d'un credit a la consommation ?",
    "Comment fonctionne l'authentification forte DSP2 ?",
    "Quels produits d'epargne propose Credit Aurore ?",
    "Welche Anforderungen stellt die BaFin an das IT-Risikomanagement ?",
    "Wie kuendige ich mein Sparkonto bei Credit Aurore ?",
    "What are the DORA incident reporting deadlines for ICT disruptions ?",
    "How is biometric data handled under CNIL recommendations ?",
    "What home and auto insurance products does Credit Aurore offer ?",
]


def _traffic_path() -> object:
    return _state_path().parent / "knowledge_traffic.json"


async def _hits(query_vec: list[float]) -> set[str]:
    found: set[str] = set()
    for corpus in _CORPORA:
        for hit in await knn_search(
            query_embedding=query_vec, corpus=corpus, language=None, top_k=_TOP_K
        ):
            if hit.score < _THRESHOLD:
                continue
            meta = hit.metadata if isinstance(hit.metadata, dict) else {}
            cat = str(meta.get("category", ""))
            if cat in _SOURCE_META:
                found.add(cat)
    return found


async def main() -> None:
    print(f"sending {len(_QUESTIONS)} banking questions through retrieval...")
    vectors = await embed(_QUESTIONS)
    now = datetime.now(UTC)
    per_cat: dict[str, list[dict[str, str]]] = {cat: [] for cat in _SOURCE_META}
    for question, vec in zip(_QUESTIONS, vectors, strict=True):
        for cat in await _hits(vec):
            per_cat[cat].append({"text": question, "time": now.isoformat()})

    categories = {
        cat: {
            "count": len(items),
            "last_used": items[-1]["time"] if items else "",
            "answers": items,
        }
        for cat, items in per_cat.items()
    }
    payload = {
        "run_at": now.strftime("%Y%m%dT%H%M%SZ"),
        "questions": len(_QUESTIONS),
        "categories": categories,
    }
    path = _traffic_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    grounded = sum(1 for c in categories.values() if c["count"])
    print(f"{grounded}/{len(_SOURCE_META)} sources grounded; wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
