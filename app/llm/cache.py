"""Exact-match response cache for LLM node calls.

Deliberately caches at the *node's already-parsed, JSON-safe result* level
(a plain dict), not raw LangChain response/message objects - those are
heterogeneous across call sites (an `AIMessage` with `.content`, a Pydantic
model instance from `with_structured_output`, a tool-call-bearing message,
...) and would need bespoke serialization per call site to round-trip
safely. A dict-only cache is one simple mechanism every node can use the
same way (see `app/graph/nodes.py`).

This only ever matches a byte-identical cache key (call kind + exact
prompt/payload content, hashed). Unlike semantic/embedding caching, there is
no "close enough" match, so there is no cross-user cache-poisoning risk to
guard against: the key IS the content, so a hit can only ever return exactly
what that exact content would have produced anyway - regardless of which
user or session originally produced it, which is safe because none of our
cache keys include anything user-identifying, only the model input itself.

In-process, in-memory, LRU-with-TTL - intentionally simple (no external
cache service to run/pay for, consistent with this project's zero-cost
infra constraint). Good enough for a single-process deployment; a multi-
process deployment would need a shared backend (e.g. the same free-tier
Postgres already used for checkpointing) to get cross-process hits, but
loses nothing correctness-wise by staying per-process - it just means fewer
cache hits, never a wrong one.
"""
import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any

_lock = threading.Lock()
_cache: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()


def make_key(*parts: str) -> str:
    """Hashes the given parts into a single cache key. Callers should pass
    one part per logical component (call kind, model tier, prompt,
    payload, ...) rather than pre-concatenating, so two different
    combinations can never accidentally collide into the same joined
    string."""
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def get(key: str) -> Any | None:
    """Returns the cached value for `key`, or None on a miss/expiry."""
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return value


def put(key: str, value: Any, *, ttl_seconds: float, max_entries: int) -> None:
    """Stores `value` under `key`, evicting the least-recently-used entry
    if this would exceed `max_entries`."""
    with _lock:
        _cache[key] = (time.monotonic() + ttl_seconds, value)
        _cache.move_to_end(key)
        while len(_cache) > max_entries:
            _cache.popitem(last=False)


def clear() -> None:
    """Drops every cached entry - used by tests to guarantee isolation
    from whatever a previous test happened to cache."""
    with _lock:
        _cache.clear()
