"""Bounded, auditable session memory for MedGuard (v3.3).

Memory is state, so it gets the discipline of a store, not of a convenient object
(Chapter 10): a defined record schema, a retention policy (TTL + a per-session
size cap), strict per-session isolation so one case can never read another's data,
and an access log so every read/write is traceable. Values are never emitted raw:
the access log records the operation and key, not the PHI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryRecord:
    session_id: str
    key: str
    value: Any
    created_at: float
    expires_at: float


@dataclass(frozen=True)
class AccessEvent:
    op: str          # "put" | "get" | "evict" | "expire"
    session_id: str
    key: str
    at: float


class SessionMemory:
    """A keyed store with retention and hard per-session isolation.

    Access is only ever granted through `session()`, which returns a view bound to
    one session id — there is no API that reads across sessions, so cross-case
    contamination is structurally impossible, not merely discouraged.
    """

    def __init__(
        self,
        *,
        ttl_s: float = 3600.0,
        max_entries_per_session: int = 64,
        clock=time.time,
    ) -> None:
        self._ttl_s = ttl_s
        self._max = max_entries_per_session
        self._clock = clock
        self._records: dict[tuple[str, str], MemoryRecord] = {}
        self.access_log: list[AccessEvent] = []

    def _log(self, op: str, session_id: str, key: str) -> None:
        self.access_log.append(AccessEvent(op, session_id, key, self._clock()))

    def _put(self, session_id: str, key: str, value: Any) -> None:
        now = self._clock()
        self._records[(session_id, key)] = MemoryRecord(
            session_id, key, value, created_at=now, expires_at=now + self._ttl_s)
        self._log("put", session_id, key)
        self._enforce_cap(session_id)

    def _get(self, session_id: str, key: str) -> Any | None:
        rec = self._records.get((session_id, key))
        if rec is None:
            return None
        if rec.expires_at <= self._clock():  # retention: expired == absent
            del self._records[(session_id, key)]
            self._log("expire", session_id, key)
            return None
        self._log("get", session_id, key)
        return rec.value

    def _enforce_cap(self, session_id: str) -> None:
        keys = [k for k in self._records if k[0] == session_id]
        while len(keys) > self._max:
            oldest = min(keys, key=lambda k: self._records[k].created_at)
            del self._records[oldest]
            self._log("evict", oldest[0], oldest[1])
            keys.remove(oldest)

    def purge_expired(self) -> int:
        """Drop all expired records; returns the number removed."""
        now = self._clock()
        expired = [k for k, r in self._records.items() if r.expires_at <= now]
        for k in expired:
            del self._records[k]
            self._log("expire", k[0], k[1])
        return len(expired)

    def session(self, session_id: str) -> "SessionView":
        return SessionView(self, session_id)


@dataclass
class SessionView:
    """A capability scoped to exactly one session — the only way to touch memory."""
    _store: SessionMemory
    session_id: str

    def put(self, key: str, value: Any) -> None:
        self._store._put(self.session_id, key, value)

    def get(self, key: str) -> Any | None:
        return self._store._get(self.session_id, key)
