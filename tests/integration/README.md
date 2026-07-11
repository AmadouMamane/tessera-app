# Integration tests

Tagged `@pytest.mark.integration` and **excluded from the gate** (`pytest -m "not
integration"`), because each one needs a live store, backend, or model that the hermetic
gate refuses to depend on. They are not dark coverage: they run in the dedicated,
non-gating **Integration** workflow (`.github/workflows/integration.yml`) — nightly and on
demand — and locally with the services up.

Run them locally:

```bash
docker compose up -d postgres     # Postgres / pgvector
make obs-up                       # ClickHouse + Prometheus + Langfuse (the spine)
make run-on-prem                  # Ollama, only for test_agent_e2e
make test-integration             # pytest tests/integration/ -m integration -ra
```

Every test **probes its dependency and skips cleanly** when it is down (`-ra` prints the
reason), so a partial stack yields skips, never errors — except where noted.

## Triage (2026-07-10 audit, P0.1)

All nine surfaces were verified present in `src/tessera` — **zero dead tests, zero
deletions**. What each needs, and where it runs:

| file | needs | runs in CI (Integration workflow) |
|---|---|---|
| `test_firewall_adapter.py` | nothing external (in-memory tool + `policy.yaml`) | ✅ always |
| `test_ledger_contract.py` | Postgres | ✅ (Postgres service) |
| `test_memory_transcript.py` | Postgres | ✅ (Postgres service) |
| `test_memory_summary.py` | Postgres | ✅ (Postgres service) |
| `test_memory_persistent.py` | Postgres + pgvector | ✅ (Postgres service) |
| `test_owned_stores_contract.py` | Postgres **and** ClickHouse (per-backend skips) | ✅ (both services) |
| `test_owned_business_events_contract.py` | ClickHouse `:8123` | ✅ (ClickHouse service) |
| `test_spine_adapters_contract.py` | Prometheus `:19090` + Langfuse `:3900` | ⏭️ **skips** — external observability backends; run locally with `make obs-up` |
| `test_agent_e2e.py` | **live on-prem LLM (Ollama)** | ⏭️ **skips** — **local-only**; needs `make run-on-prem`, never a runner |

The workflow stands up **Postgres and ClickHouse** as services (the two owned durable
stores; the ClickHouse adapter `CREATE DATABASE/TABLE IF NOT EXISTS` on first use, so no
init step is needed). Prometheus, Langfuse and Ollama are deliberately **not** provisioned
on a runner — a full Langfuse stack or a local model on CI would be disproportionate, and
those contracts read backends Tessera does not own. Their tests skip, visibly.
