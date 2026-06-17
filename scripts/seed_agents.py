"""Seed ~30 days of realistic per-agent conversation history (multi-agent Phase 1).

Writes durable rows into ``conversation_messages`` (the transcript that drives
the per-agent Synthèse), backdated over the last 30 days and stamped with each
agent's ``agent_id``. It also plants a handful of **shared conversations** where a
single ``conversation_id`` carries turns from two agents (a handoff), so per-turn
attribution and dedup can be tested.

The seed is **idempotent**: every seeded ``conversation_id`` is derived from a
fixed UUIDv5 namespace, so a re-run deletes-then-reinserts only its own rows and
never touches real traffic (which uses random UUIDs). Numbers are not faked — the
Synthèse reflects exactly what is seeded, at the turn grain.

Run: ``uv run python scripts/seed_agents.py`` (needs the local Postgres up).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from psycopg import sql

from tessera.agent.registry import can_handoff, list_agents
from tessera.memory.transcript import ensure_transcript_schema
from tessera.observability.logging import get_logger
from tessera.retrieval.store import get_pool

LOG = get_logger("tessera.seed_agents")

# One INSERT row:
# (conversation_id, turn_id, seq, agent_id, role, content, name, created_at, latency_ms).
Row = tuple[uuid.UUID, uuid.UUID, int, str, str, str, str | None, datetime, float | None]

# Per-agent latency profile (ms) for the SYNTHETIC demo history — so the observable
# latency KPI genuinely differs per agent. Real turns capture real latency via the
# transcript's latency_ms column; only this seeded demo data is synthetic.
_LATENCY_MS: dict[str, float] = {
    "support-client": 2400.0,
    "onboarding": 3300.0,
    "recouvrement": 4600.0,
}


def _latency(agent_id: str, rng: random.Random) -> float:
    base = _LATENCY_MS.get(agent_id, 3000.0)
    return round(base + rng.uniform(-600, 900), 1)

# Fixed namespace so seeded conversation ids are deterministic + collision-free
# with real traffic. Bump the suffix to invalidate a previous seed generation.
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "tessera/seed/agents/v1")
_DAYS = 30
_PER_AGENT = 40  # conversations per agent over the window
_SHARED = 6  # handoff conversations (support-client -> onboarding)
_SEED = 20260617

# Per-agent conversation pool: (user question, assistant answer). The answer text
# carries the escalation heuristic words (conseiller/ticket/transf) where relevant,
# so the Synthèse "escaladé" detection lights up on the right rows.
_POOLS: dict[str, list[tuple[str, str]]] = {
    "support-client": [
        (
            "Quel est mon solde ?",
            "Votre solde courant est de 1 240,50 €. Souhaitez-vous le détail des dernières "
            "opérations ?",
        ),
        (
            "Je veux bloquer ma carte, je l'ai perdue.",
            "J'ai noté votre demande de blocage. Pour votre sécurité je transmets le dossier à un "
            "conseiller. Référence ticket : TS-4F2A.",
        ),
        (
            "Comment exercer mon droit à l'effacement RGPD ?",
            "Le droit à l'effacement (art. 17 RGPD) permet de demander la suppression de vos "
            "données, sous réserve des durées légales de conservation bancaire.",
        ),
        (
            "Affichez mes 5 dernières transactions.",
            "Voici vos 5 dernières opérations : -42,30 € (courses), -9,99 € (abonnement), "
            "+1 800,00 € (salaire), -60,00 € (retrait), -15,40 € (transport).",
        ),
        (
            "Mon virement n'est pas arrivé, que faire ?",
            "Un virement SEPA peut prendre 1 jour ouvré. S'il dépasse ce délai, je transfère votre "
            "dossier à un conseiller pour investigation.",
        ),
    ],
    "onboarding": [
        (
            "Quelles pièces pour ouvrir un compte ?",
            "Il vous faut une pièce d'identité en cours de validité et un justificatif de domicile "
            "de moins de 3 mois.",
        ),
        (
            "Suis-je éligible à l'ouverture d'un compte ?",
            "L'éligibilité dépend de votre résidence dans l'UE et de la vérification KYC. Je peux "
            "lancer le parcours si vous le souhaitez.",
        ),
        (
            "Simulez un crédit de 10 000 € sur 24 mois.",
            "Pour 10 000 € sur 24 mois au TAEG indicatif de 4,9 %, la mensualité estimée est "
            "d'environ 438 €. Une simulation détaillée est disponible.",
        ),
        (
            "Combien de temps pour valider mon dossier KYC ?",
            "La vérification KYC prend en général 24 à 48 h après réception des justificatifs.",
        ),
        (
            "Mon dossier KYC a été refusé, que faire ?",
            "Votre vérification KYC n'a pas abouti faute de justificatif lisible. Je transmets "
            "votre dossier à un conseiller onboarding qui vous recontactera. Référence : TS-9B33.",
        ),
    ],
    "recouvrement": [
        (
            "J'ai reçu une relance, pourquoi ?",
            "Une échéance du 05/06 reste impayée (220 €). Souhaitez-vous mettre en place un "
            "échéancier ?",
        ),
        (
            "Je ne peux pas payer ce mois-ci.",
            "Je comprends votre situation. Je transmets votre dossier à un conseiller recouvrement "
            "qui étudiera un report. Référence : TS-7C19.",
        ),
        (
            "Quel est mon montant dû à ce jour ?",
            "Le montant total dû est de 460 €, dont 220 € en retard depuis le 05/06.",
        ),
        (
            "Puis-je étaler le remboursement ?",
            "Un échéancier sur 3 mois est possible. Un conseiller peut le formaliser avec vous.",
        ),
        (
            "À quelle date dois-je régler mon échéance ?",
            "Votre prochaine échéance de 220 € est due le 05/07. Vous pouvez la régler directement "
            "depuis votre espace client.",
        ),
    ],
}

# Shared (handoff) conversation script: turns alternate between two agents.
_HANDOFF = [
    (
        "support-client",
        "Bonjour, je suis déjà client mais je voudrais ouvrir un deuxième compte.",
        "Bonjour ! L'ouverture d'un nouveau compte est gérée par notre équipe Onboarding. "
        "Je vous transfère, ils prennent le relais tout de suite.",
    ),
    (
        "onboarding",
        "D'accord, de quelles pièces ai-je besoin ?",
        "Bien sûr — une pièce d'identité valide et un justificatif de domicile de moins de 3 mois "
        "suffisent pour démarrer le dossier.",
    ),
]


def _conv_id(tag: str) -> uuid.UUID:
    return uuid.uuid5(_NS, tag)


def _rows_for_agent(agent_id: str, rng: random.Random, now: datetime) -> list[Row]:
    """Build INSERT tuples for one agent's standalone conversations."""
    pool = _POOLS[agent_id]
    rows: list[Row] = []
    for i in range(_PER_AGENT):
        conv = _conv_id(f"{agent_id}:{i}")
        # Spread start times across the 30-day window, business-ish hours.
        day = rng.randint(0, _DAYS - 1)
        start = now - timedelta(days=day, hours=rng.randint(0, 9), minutes=rng.randint(0, 59))
        turns = rng.randint(1, 3)
        for t in range(turns):
            q, a = rng.choice(pool)
            turn_id = uuid.uuid5(_NS, f"{conv}:{t}")
            ts = start + timedelta(minutes=2 * t)
            rows.append((conv, turn_id, 0, agent_id, "user", q, None, ts, None))
            rows.append(
                (
                    conv,
                    turn_id,
                    1,
                    agent_id,
                    "assistant",
                    a,
                    None,
                    ts + timedelta(seconds=20),
                    _latency(agent_id, rng),
                )
            )
    return rows


def _rows_for_shared(rng: random.Random, now: datetime) -> list[Row]:
    """Build INSERT tuples for shared handoff conversations (2 agents, 1 conv)."""
    rows: list[Row] = []
    for i in range(_SHARED):
        conv = _conv_id(f"shared:{i}")
        start = now - timedelta(days=rng.randint(0, _DAYS - 1), hours=rng.randint(0, 9))
        for t, (agent_id, q, a) in enumerate(_HANDOFF):
            turn_id = uuid.uuid5(_NS, f"{conv}:{t}")
            ts = start + timedelta(minutes=3 * t)
            rows.append((conv, turn_id, 0, agent_id, "user", q, None, ts, None))
            rows.append(
                (
                    conv,
                    turn_id,
                    1,
                    agent_id,
                    "assistant",
                    a,
                    None,
                    ts + timedelta(seconds=25),
                    _latency(agent_id, rng),
                )
            )
    return rows


async def seed(*, dry_run: bool = False) -> dict[str, int]:
    """(Re)seed the per-agent transcript. Returns a small stats dict."""
    await ensure_transcript_schema()  # applies the agent_id column migration if needed

    agents = [a.id for a in list_agents()]
    rng = random.Random(_SEED)  # noqa: S311  deterministic demo data, not crypto
    now = datetime.now(UTC)

    rows: list[Row] = []
    for agent_id in agents:
        if agent_id in _POOLS:
            rows.extend(_rows_for_agent(agent_id, rng, now))
    shared_rows = _rows_for_shared(rng, now)
    rows.extend(shared_rows)

    conv_ids = sorted({r[0] for r in rows})
    stats = {
        "agents": len(agents),
        "messages": len(rows),
        "conversations": len(conv_ids),
        "shared": _SHARED,
        "handoff_ok": int(can_handoff("support-client", "onboarding")),
    }
    LOG.info("seed.plan", **stats)
    if dry_run:
        return stats

    pool = get_pool()
    if pool.closed:
        await pool.open()
    insert = sql.SQL(
        "INSERT INTO conversation_messages "
        "(conversation_id, turn_id, seq, agent_id, role, content, name, created_at, latency_ms) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        # Idempotent: drop this seed generation's rows, then reinsert.
        await cur.execute(
            "DELETE FROM conversation_messages WHERE conversation_id = ANY(%s);",
            (conv_ids,),
        )
        await cur.executemany(insert, rows)
        await conn.commit()
    LOG.info("seed.done", **stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed per-agent demo conversations.")
    parser.add_argument("--dry-run", action="store_true", help="plan only, no DB writes")
    args = parser.parse_args()
    stats = asyncio.run(seed(dry_run=args.dry_run))
    print(
        f"agents={stats['agents']} conversations={stats['conversations']} "
        f"messages={stats['messages']} shared={stats['shared']} "
        f"handoff_ok={stats['handoff_ok']}"
    )


if __name__ == "__main__":
    main()
