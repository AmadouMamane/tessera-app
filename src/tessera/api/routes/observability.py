from typing import Any

import structlog
from fastapi import APIRouter, Body

router = APIRouter(prefix="/observability", tags=["observability"])
logger = structlog.get_logger("tessera.api.observability")

@router.post("/log")
async def log_client_event(payload: dict[str, Any] = Body(...)) -> dict[str, str]:
    """Ingest frontend telemetry (Web Vitals, crashes, interaction events).
    
    Routes these logs into the backend's Structlog pipeline, which is
    already configured for GCP Cloud Logging and Error Reporting.
    """
    event_type = payload.get("type", "client_event")
    level = payload.get("level", "info")

    # Format for GCP Error Reporting if it's an error
    if level == "error":
        # Using GCP's specific type for Error Reporting
        payload["@type"] = "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"
        logger.error(f"Frontend Error: {event_type}", **payload)
    elif level == "warning":
        logger.warning(f"Frontend Warning: {event_type}", **payload)
    else:
        logger.info(f"Frontend Telemetry: {event_type}", **payload)

    return {"status": "ok"}

@router.post("/replay/{trace_id}")
async def replay_langfuse_trace(trace_id: str) -> dict[str, Any]:
    """Time-Travel Replay endpoint.
    
    Fetches the full trace from Langfuse and simulates re-running the 
    exact LangGraph state for debugging purposes.
    """
    import os

    from langfuse import Langfuse

    lf = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3080")
    )

    try:
        trace = lf.api.trace.get(trace_id)
        if not trace:
            return {"error": "Trace not found"}

        # We must re-hydrate the graph state. Since `trace.input` may be None
        # for standard callbacks, we extract it from the transcript database
        # using the session_id (conversation) and thread_id (turn).
        session_id = trace.metadata.get("session_id")
        thread_id = trace.metadata.get("thread_id")
        if not session_id or not thread_id:
            return {"error": "Trace metadata missing session_id or thread_id"}
        
        tags = trace.tags or []
        lang = "en"
        for t in tags:
            if t.startswith("lang:"):
                lang = t.split("lang:", 1)[1]
        model = None
        for t in tags:
            if t.startswith("model:"):
                model = t.split("model:", 1)[1]

        import uuid
        from tessera.retrieval.store import get_pool
        from psycopg import sql
        from psycopg.rows import dict_row

        conv_uuid = uuid.UUID(session_id)
        turn_uuid = uuid.UUID(thread_id)

        # 1. Fetch the exact user input for this turn
        pool = get_pool()
        if pool.closed:
            await pool.open()
            
        async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, content FROM conversation_messages WHERE conversation_id = %s AND turn_id = %s AND role = 'user' ORDER BY seq ASC LIMIT 1",
                (conv_uuid, turn_uuid)
            )
            user_msg_row = await cur.fetchone()
            if not user_msg_row:
                return {"error": "User message not found in transcript for this turn"}
                
            user_input = user_msg_row["content"]
            user_msg_id = user_msg_row["id"]
            
            # 2. Fetch prior messages before this turn
            await cur.execute(
                "SELECT role, content, name, created_at FROM conversation_messages WHERE conversation_id = %s AND id < %s ORDER BY id ASC",
                (conv_uuid, user_msg_id)
            )
            prior_rows = await cur.fetchall()

        from tessera.agent.state import ConversationMessage
        prior_messages = [
            ConversationMessage(
                role=r["role"],
                content=str(r["content"]),
                timestamp=r["created_at"],
                name=r["name"]
            ) for r in prior_rows
        ]

        # 3. Re-invoke the agent graph synchronously (without reporter streaming)
        from tessera.agent.state import new_state
        from tessera.api.routes.chat import _streaming_graph
        
        replay_turn_id = uuid.uuid4()
        initial = new_state(
            conversation_id=conv_uuid,
            turn_id=replay_turn_id,
            user_input=user_input,
            language=lang, # type: ignore
            language_confidence=1.0,
            prior_messages=prior_messages,
            subject_id=trace.metadata.get("user_id"),
            model=model,
        )

        config: dict[str, object] = {
            "configurable": {"thread_id": f"replay-{trace_id}"},
            "tags": ["chat", f"model:{model or 'default'}", f"lang:{lang}", "replay"],
            "metadata": {
                "session_id": str(conv_uuid),
                "user_id": trace.metadata.get("user_id"),
                "replayed_from": trace_id
            },
        }

        try:
            from langfuse.langchain import CallbackHandler
            langfuse_handler = CallbackHandler()
            config["callbacks"] = [langfuse_handler]
        except ImportError:
            pass

        graph = _streaming_graph()
        await graph.ainvoke(initial, config=config) # type: ignore
        snapshot = graph.get_state(config) # type: ignore
        state = snapshot.values

        # If it paused at reporter, simulate reporter rendering
        from tessera.agent.state import NodeName
        from tessera.agent import reporter as reporter_module
        if NodeName.REPORTER.value in (snapshot.next or ()):
            draft = state.get("draft_response", "")
            if draft:
                final_response = reporter_module.render(state)
            else:
                from tessera.agent.reporter import _FALLBACK_RESPONSES
                final_response = _FALLBACK_RESPONSES[state.get("language", "en")]
        else:
            final_response = str(state.get("final_response", ""))

        import asyncio
        if "callbacks" in config and config["callbacks"]:
            handler = config["callbacks"][0]
            if hasattr(handler, "_langfuse_client"):
                await asyncio.to_thread(handler._langfuse_client.flush)

        return {
            "status": "replayed",
            "trace_id": trace_id,
            "inputs": user_input,
            "outputs": final_response,
            "message": "LangGraph state successfully rehydrated and executed."
        }
    except Exception as e:
        logger.error(f"Replay failed for trace {trace_id}", error=str(e))
        return {"error": str(e)}
