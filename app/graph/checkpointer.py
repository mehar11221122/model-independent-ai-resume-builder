"""Durable checkpoint storage so a workflow can pause (e.g. waiting on a
follow-up-question answer from the user) and resume later without losing
state. Backend is a config choice (memory / sqlite / postgres), matching the
scope doc's "Redis or PostgreSQL" requirement - sqlite is used for local dev
so the project runs with zero extra infrastructure, postgres is a
drop-in swap for production.
"""
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import get_settings


@lru_cache
def get_checkpointer() -> BaseCheckpointSaver:
    settings = get_settings()

    if settings.checkpoint_backend == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if settings.checkpoint_backend == "sqlite":
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = Path(settings.sqlite_checkpoint_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # `from_conn_string` is a contextmanager meant for short-lived `with`
        # blocks; the app needs the connection to live for its whole
        # lifetime, so open it directly instead (same pattern the
        # contextmanager uses internally).
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        return SqliteSaver(conn)

    if settings.checkpoint_backend == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver.from_conn_string(settings.postgres_dsn)
        saver.setup()
        return saver

    raise ValueError(f"Unknown checkpoint backend: {settings.checkpoint_backend}")
