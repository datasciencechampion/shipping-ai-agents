"""Tests for v3.3 bounded, auditable, isolated session memory."""

from medguard.memory import SessionMemory


class _Clock:
    """A controllable clock so retention is deterministic."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_put_and_get_within_same_session():
    mem = SessionMemory()
    s = mem.session("case-1")
    s.put("egfr", 22)
    assert s.get("egfr") == 22


def test_sessions_are_isolated():
    mem = SessionMemory()
    a = mem.session("case-a")
    b = mem.session("case-b")
    a.put("drug", "gabapentin")
    # b cannot see a's data — cross-case contamination is structurally impossible.
    assert b.get("drug") is None


def test_retention_expires_old_records():
    clock = _Clock()
    mem = SessionMemory(ttl_s=60.0, clock=clock)
    s = mem.session("case-1")
    s.put("k", "v")
    clock.advance(61.0)
    assert s.get("k") is None  # expired == absent


def test_purge_expired_reports_count():
    clock = _Clock()
    mem = SessionMemory(ttl_s=10.0, clock=clock)
    mem.session("c").put("a", 1)
    mem.session("c").put("b", 2)
    clock.advance(11.0)
    assert mem.purge_expired() == 2


def test_size_cap_evicts_oldest():
    clock = _Clock()
    mem = SessionMemory(max_entries_per_session=2, clock=clock)
    s = mem.session("c")
    s.put("k1", 1); clock.advance(1)
    s.put("k2", 2); clock.advance(1)
    s.put("k3", 3)  # exceeds cap of 2 -> oldest (k1) evicted
    assert s.get("k1") is None
    assert s.get("k2") == 2
    assert s.get("k3") == 3


def test_access_log_records_ops_but_not_values():
    mem = SessionMemory()
    s = mem.session("case-1")
    s.put("mrn", "SECRET-123")
    s.get("mrn")
    ops = [(e.op, e.session_id, e.key) for e in mem.access_log]
    assert ("put", "case-1", "mrn") in ops
    assert ("get", "case-1", "mrn") in ops
    # The raw PHI value is never written to the audit log.
    assert all("SECRET-123" not in str(e) for e in mem.access_log)
