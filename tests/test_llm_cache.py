"""Unit tests for the exact-match LLM response cache (`app/llm/cache.py`)."""
import time

from app.llm import cache as llm_cache


def test_miss_on_unknown_key():
    assert llm_cache.get("nonexistent") is None


def test_put_then_get_round_trips_value():
    key = llm_cache.make_key("kind", "a", "b")
    llm_cache.put(key, {"hello": "world"}, ttl_seconds=60, max_entries=10)
    assert llm_cache.get(key) == {"hello": "world"}


def test_make_key_is_deterministic_and_distinguishes_parts():
    key1 = llm_cache.make_key("extract", "resume", "prompt text", "input text")
    key2 = llm_cache.make_key("extract", "resume", "prompt text", "input text")
    key3 = llm_cache.make_key("extract", "resume", "prompt text", "different input")
    assert key1 == key2
    assert key1 != key3


def test_make_key_does_not_collide_across_part_boundaries():
    # "ab" + "c" vs "a" + "bc" must not hash the same just because their
    # naive concatenation would be identical.
    key1 = llm_cache.make_key("ab", "c")
    key2 = llm_cache.make_key("a", "bc")
    assert key1 != key2


def test_expired_entry_is_evicted_on_read():
    key = llm_cache.make_key("kind", "expires-fast")
    llm_cache.put(key, "value", ttl_seconds=0.01, max_entries=10)
    time.sleep(0.05)
    assert llm_cache.get(key) is None


def test_lru_eviction_drops_oldest_when_over_capacity():
    llm_cache.put(llm_cache.make_key("k", "1"), "v1", ttl_seconds=60, max_entries=2)
    llm_cache.put(llm_cache.make_key("k", "2"), "v2", ttl_seconds=60, max_entries=2)
    llm_cache.put(llm_cache.make_key("k", "3"), "v3", ttl_seconds=60, max_entries=2)

    assert llm_cache.get(llm_cache.make_key("k", "1")) is None  # evicted
    assert llm_cache.get(llm_cache.make_key("k", "2")) == "v2"
    assert llm_cache.get(llm_cache.make_key("k", "3")) == "v3"


def test_get_refreshes_recency_so_it_is_not_the_next_eviction():
    llm_cache.put(llm_cache.make_key("k", "1"), "v1", ttl_seconds=60, max_entries=2)
    llm_cache.put(llm_cache.make_key("k", "2"), "v2", ttl_seconds=60, max_entries=2)
    llm_cache.get(llm_cache.make_key("k", "1"))  # touch "1", making "2" the LRU entry
    llm_cache.put(llm_cache.make_key("k", "3"), "v3", ttl_seconds=60, max_entries=2)

    assert llm_cache.get(llm_cache.make_key("k", "1")) == "v1"
    assert llm_cache.get(llm_cache.make_key("k", "2")) is None  # evicted instead
    assert llm_cache.get(llm_cache.make_key("k", "3")) == "v3"


def test_clear_removes_everything():
    llm_cache.put(llm_cache.make_key("k", "1"), "v1", ttl_seconds=60, max_entries=10)
    llm_cache.clear()
    assert llm_cache.get(llm_cache.make_key("k", "1")) is None
