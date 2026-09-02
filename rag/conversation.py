"""Server-owned conversation state with optimistic versioning and pluggable persistence."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass
class ConversationState:
    session_id: str
    owner_id: str | None = None
    tenant_id: str = "default"
    lane: str | None = None
    task_status: str = "active"
    entities: dict[str, list[str]] = field(default_factory=dict)
    confirmed_slots: dict[str, str] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    recent_turns: list[dict[str, str]] = field(default_factory=list)
    clarification_count: int = 0
    tool_status: dict[str, str] = field(default_factory=dict)
    escalation_id: str | None = None
    version: int = 0
    updated_at: float = field(default_factory=time.time)


class StateConflict(RuntimeError):
    pass


class ConversationStore(Protocol):
    def get(self, session_id: str) -> ConversationState | None: ...
    def save(self, state: ConversationState, *, expected_version: int | None = None) -> None: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._items: dict[str, ConversationState] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> ConversationState | None:
        with self._lock:
            item = self._items.get(session_id)
            return ConversationState(**asdict(item)) if item else None

    def save(self, state: ConversationState, *, expected_version: int | None = None) -> None:
        with self._lock:
            current = self._items.get(state.session_id)
            actual = current.version if current else 0
            if expected_version is not None and actual != expected_version:
                raise StateConflict(f"expected version {expected_version}, found {actual}")
            state.version = actual + 1
            state.updated_at = time.time()
            self._items[state.session_id] = ConversationState(**asdict(state))


class SQLiteConversationStore:
    """Durable local adapter; production can replace it with Postgres behind the same contract."""
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        with sqlite3.connect(path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS conversations ("
                        "session_id TEXT PRIMARY KEY, version INTEGER NOT NULL, "
                        "updated_at REAL NOT NULL, state_json TEXT NOT NULL)")

    def get(self, session_id: str) -> ConversationState | None:
        with sqlite3.connect(self.path) as con:
            row = con.execute("SELECT state_json FROM conversations WHERE session_id = ?",
                              (session_id,)).fetchone()
        return ConversationState(**json.loads(row[0])) if row else None

    def save(self, state: ConversationState, *, expected_version: int | None = None) -> None:
        with self._lock, sqlite3.connect(self.path) as con:
            row = con.execute("SELECT version FROM conversations WHERE session_id = ?",
                              (state.session_id,)).fetchone()
            actual = int(row[0]) if row else 0
            if expected_version is not None and actual != expected_version:
                raise StateConflict(f"expected version {expected_version}, found {actual}")
            state.version = actual + 1
            state.updated_at = time.time()
            payload = json.dumps(asdict(state), ensure_ascii=False)
            con.execute("INSERT INTO conversations VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(session_id) DO UPDATE SET version=excluded.version, "
                        "updated_at=excluded.updated_at, state_json=excluded.state_json",
                        (state.session_id, state.version, state.updated_at, payload))


class RedisConversationStore:
    """Atomic shared state adapter with an injected Redis client."""
    _SAVE = """
local current = redis.call('GET', KEYS[1])
local actual = 0
if current then actual = tonumber(cjson.decode(current)['version'] or 0) end
if tonumber(ARGV[1]) >= 0 and actual ~= tonumber(ARGV[1]) then return -1 end
redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[3]))
return actual + 1
"""

    def __init__(self, client, *, prefix: str = "shopping:conversation:",
                 ttl_s: int = 86400) -> None:
        self.client = client
        self.prefix = prefix
        self.ttl_s = ttl_s

    def _key(self, session_id: str) -> str:
        return self.prefix + session_id

    def get(self, session_id: str) -> ConversationState | None:
        raw = self.client.get(self._key(session_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return ConversationState(**json.loads(raw))

    def save(self, state: ConversationState, *, expected_version: int | None = None) -> None:
        expected = -1 if expected_version is None else expected_version
        state.updated_at = time.time()
        state.version = (expected_version or 0) + 1
        payload = json.dumps(asdict(state), ensure_ascii=False)
        result = int(self.client.eval(self._SAVE, 1, self._key(state.session_id), expected,
                                      payload, self.ttl_s))
        if result < 0:
            raise StateConflict("redis conversation version changed")
        state.version = result


class PostgresConversationStore:
    """Postgres adapter using an injected DB-API connection factory."""
    def __init__(self, connect) -> None:
        self._connect = connect
        with self._connect() as con, con.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS conversation_state ("
                        "session_id TEXT PRIMARY KEY, version BIGINT NOT NULL, "
                        "updated_at DOUBLE PRECISION NOT NULL, state_json JSONB NOT NULL)")
            con.commit()

    def get(self, session_id: str) -> ConversationState | None:
        with self._connect() as con, con.cursor() as cur:
            cur.execute("SELECT state_json FROM conversation_state WHERE session_id = %s",
                        (session_id,))
            row = cur.fetchone()
        if not row:
            return None
        payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return ConversationState(**payload)

    def save(self, state: ConversationState, *, expected_version: int | None = None) -> None:
        with self._connect() as con, con.cursor() as cur:
            cur.execute("SELECT version FROM conversation_state WHERE session_id = %s FOR UPDATE",
                        (state.session_id,))
            row = cur.fetchone()
            actual = int(row[0]) if row else 0
            if expected_version is not None and actual != expected_version:
                con.rollback()
                raise StateConflict(f"expected version {expected_version}, found {actual}")
            state.version = actual + 1
            state.updated_at = time.time()
            payload = json.dumps(asdict(state), ensure_ascii=False)
            cur.execute("INSERT INTO conversation_state VALUES (%s, %s, %s, %s::jsonb) "
                        "ON CONFLICT(session_id) DO UPDATE SET version=excluded.version, "
                        "updated_at=excluded.updated_at, state_json=excluded.state_json",
                        (state.session_id, state.version, state.updated_at, payload))
            con.commit()


def make_conversation_store(backend: str, *, sqlite_path: str = ".sessions.db",
                            redis_url: str = "", postgres_dsn: str = "") -> ConversationStore:
    backend = (backend or "memory").strip().lower()
    if backend == "memory":
        return InMemoryConversationStore()
    if backend == "sqlite":
        return SQLiteConversationStore(sqlite_path)
    if backend == "redis":
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("SESSION_BACKEND=redis requires the production extra") from exc
        return RedisConversationStore(redis.Redis.from_url(redis_url, decode_responses=False))
    if backend == "postgres":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("SESSION_BACKEND=postgres requires the production extra") from exc
        return PostgresConversationStore(lambda: psycopg.connect(postgres_dsn))
    raise ValueError(f"unknown conversation backend: {backend}")


def new_session_id() -> str:
    return uuid.uuid4().hex
