"""Call an observability route handler uniformly, whether it is sync or async.

The observability READ handlers are synchronous ``def`` now — Starlette runs them in its
threadpool so a dashboard's ~25 concurrent reads don't serialize on the event loop. A few
(the snapshot batchers, the async-psycopg readers) legitimately stay ``async``. Tests that call
a handler directly (to compare it against the batched snapshot, etc.) use this so the calling
convention doesn't have to know which shape a given route is.
"""

from __future__ import annotations

import inspect
from typing import Any


async def call_route(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Invoke ``fn``, awaiting its result only if it is a coroutine/awaitable."""
    result = fn(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result
