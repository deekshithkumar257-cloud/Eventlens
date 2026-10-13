"""SQLite persistence for imports, normalized events and alerts.

Tables are created automatically on startup (init_db), so the backend can be
restarted without losing stored records. Database location is controlled by
EVENTLENS_DB_PATH (relative paths resolve against backend/).

Duplicate handling:
- Each event gets a deterministic event_id derived from its normalized content.
  Inserting an event whose event_id already exists is ignored and counted as a
  duplicate, so re-uploading the same file never creates duplicate events.
- Alerts are a deterministic function of the stored events. After each import
  the alert table is rebuilt in the same transaction, so unchanged data yields
  identical alert IDs and no duplicate alerts.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import DetectedAlert, NormalizedEvent

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "eventlens.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    import_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    source_format TEXT NOT NULL,
    total_records INTEGER NOT NULL,
    inserted_events INTEGER NOT NULL,
    duplicate_events INTEGER NOT NULL,
    rejected_records INTEGER NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    source TEXT,
    event_type TEXT NOT NULL,
    user TEXT,
    source_ip TEXT,
    source_host TEXT,
    destination_host TEXT,
    destination_ip TEXT,
    port INTEGER,
    protocol TEXT,
    severity TEXT NOT NULL,
    raw TEXT NOT NULL,
    import_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user);
CREATE INDEX IF NOT EXISTS idx_events_source_ip ON events(source_ip);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    priority TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    observed TEXT NOT NULL,
    uncertain TEXT NOT NULL,
    next_step TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_value TEXT NOT NULL,
    affected_user TEXT,
    affected_source_ip TEXT,
    affected_host TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    evidence_factors TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority);
CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id);

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id TEXT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    position INTEGER NOT NULL,
    role TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (alert_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_alert_events_event ON alert_events(event_id);
"""

EVENT_COLUMNS = (
    "event_id", "timestamp", "source", "event_type", "user", "source_ip", "source_host",
    "destination_host", "destination_ip", "port", "protocol", "severity", "raw", "import_id",
)


def get_db_path() -> Path:
    raw = os.getenv("EVENTLENS_DB_PATH", "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection; commit on success, roll back on any exception."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with transaction(path) as conn:
        conn.executescript(SCHEMA)


# ---- Events -------------------------------------------------------------------
def insert_events(conn: sqlite3.Connection, events: list[NormalizedEvent], import_id: str) -> tuple[int, int]:
    """Insert events, ignoring ones already stored. Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0
    for event in events:
        cur = conn.execute(
            "INSERT OR IGNORE INTO events (event_id, timestamp, source, event_type, user, source_ip, "
            "source_host, destination_host, destination_ip, port, protocol, severity, raw, import_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id, event.timestamp, event.source, event.event_type, event.user,
                event.source_ip, event.source_host, event.destination_host, event.destination_ip,
                event.port, event.protocol, event.severity,
                json.dumps(event.raw, ensure_ascii=False), import_id,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            duplicates += 1
    return inserted, duplicates


def record_import(
    conn: sqlite3.Connection, *, import_id: str, file_name: str, source_format: str,
    total_records: int, inserted: int, duplicates: int, rejected: int, imported_at: str,
) -> None:
    conn.execute(
        "INSERT INTO imports (import_id, file_name, source_format, total_records, inserted_events, "
        "duplicate_events, rejected_records, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (import_id, file_name, source_format, total_records, inserted, duplicates, rejected, imported_at),
    )


def row_to_event(row: sqlite3.Row) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=row["event_id"],
        timestamp=row["timestamp"],
        source=row["source"],
        event_type=row["event_type"],
        user=row["user"],
        source_ip=row["source_ip"],
        source_host=row["source_host"],
        destination_host=row["destination_host"],
        destination_ip=row["destination_ip"],
        port=row["port"],
        protocol=row["protocol"],
        severity=row["severity"],
        raw=json.loads(row["raw"]),
    )


def fetch_all_events(conn: sqlite3.Connection) -> list[NormalizedEvent]:
    rows = conn.execute("SELECT * FROM events ORDER BY timestamp, event_id").fetchall()
    return [row_to_event(r) for r in rows]


def _where(clauses: list[tuple[str, list[Any]]]) -> tuple[str, list[Any]]:
    if not clauses:
        return "", []
    sql = " WHERE " + " AND ".join(c for c, _ in clauses)
    params: list[Any] = []
    for _, p in clauses:
        params.extend(p)
    return sql, params


def list_events(
    conn: sqlite3.Connection, *, limit: int, offset: int,
    event_type: str | None = None, user: str | None = None, source_ip: str | None = None,
    severity: str | None = None, query: str | None = None,
) -> tuple[list[NormalizedEvent], int]:
    clauses: list[tuple[str, list[Any]]] = []
    if event_type:
        clauses.append(("event_type = ?", [event_type]))
    if user:
        clauses.append(("user = ?", [user]))
    if source_ip:
        clauses.append(("source_ip = ?", [source_ip]))
    if severity:
        clauses.append(("severity = ?", [severity]))
    if query:
        like = f"%{_escape_like(query)}%"
        clauses.append((
            "(event_id LIKE ? ESCAPE '\\' OR user LIKE ? ESCAPE '\\' OR source_ip LIKE ? ESCAPE '\\' "
            "OR source_host LIKE ? ESCAPE '\\' OR destination_host LIKE ? ESCAPE '\\' "
            "OR destination_ip LIKE ? ESCAPE '\\')",
            [like] * 6,
        ))
    where, params = _where(clauses)
    total = conn.execute(f"SELECT COUNT(*) FROM events{where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM events{where} ORDER BY timestamp DESC, event_id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return [row_to_event(r) for r in rows], total


def get_events_by_ids(conn: sqlite3.Connection, event_ids: list[str]) -> dict[str, NormalizedEvent]:
    if not event_ids:
        return {}
    placeholders = ",".join("?" for _ in event_ids)
    rows = conn.execute(f"SELECT * FROM events WHERE event_id IN ({placeholders})", event_ids).fetchall()
    return {r["event_id"]: row_to_event(r) for r in rows}


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---- Alerts -------------------------------------------------------------------
def replace_alerts(conn: sqlite3.Connection, alerts: list[DetectedAlert], created_at: str) -> tuple[int, int]:
    """Rebuild the alert table from the latest detection run.

    Returns (new_alert_count, total_alert_count). "New" means the alert ID was not
    present before this run, so an unchanged dataset reports zero new alerts.
    """
    before = {r[0] for r in conn.execute("SELECT alert_id FROM alerts")}
    conn.execute("DELETE FROM alert_events")
    conn.execute("DELETE FROM alerts")
    for alert in alerts:
        conn.execute(
            "INSERT INTO alerts (alert_id, fingerprint, rule_id, rule_name, priority, title, summary, "
            "observed, uncertain, next_step, entity_type, entity_value, affected_user, "
            "affected_source_ip, affected_host, first_seen, last_seen, event_count, "
            "evidence_factors, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                alert.alert_id, alert.fingerprint, alert.rule_id, alert.rule_name, alert.priority,
                alert.title, alert.summary, alert.observed, alert.uncertain, alert.next_step,
                alert.entity_type, alert.entity_value, alert.affected_user, alert.affected_source_ip,
                alert.affected_host, alert.first_seen, alert.last_seen, len(alert.evidence),
                json.dumps(alert.evidence_factors, ensure_ascii=False), created_at,
            ),
        )
        for link in alert.evidence:
            conn.execute(
                "INSERT INTO alert_events (alert_id, event_id, position, role, reason) VALUES (?, ?, ?, ?, ?)",
                (alert.alert_id, link.event_id, link.position, link.role, link.reason),
            )
    after = {a.alert_id for a in alerts}
    return len(after - before), len(after)


def _alert_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "alert_id": row["alert_id"],
        "rule_id": row["rule_id"],
        "rule_name": row["rule_name"],
        "priority": row["priority"],
        "title": row["title"],
        "entity_type": row["entity_type"],
        "entity_value": row["entity_value"],
        "affected_user": row["affected_user"],
        "affected_source_ip": row["affected_source_ip"],
        "affected_host": row["affected_host"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "event_count": row["event_count"],
        "created_at": row["created_at"],
    }


def list_alerts(
    conn: sqlite3.Connection, *, limit: int, offset: int,
    priority: str | None = None, rule_id: str | None = None, query: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[tuple[str, list[Any]]] = []
    if priority:
        clauses.append(("priority = ?", [priority]))
    if rule_id:
        clauses.append(("rule_id = ?", [rule_id]))
    if query:
        like = f"%{_escape_like(query)}%"
        clauses.append((
            "(title LIKE ? ESCAPE '\\' OR entity_value LIKE ? ESCAPE '\\' OR rule_name LIKE ? ESCAPE '\\' "
            "OR affected_user LIKE ? ESCAPE '\\' OR affected_source_ip LIKE ? ESCAPE '\\' "
            "OR alert_id LIKE ? ESCAPE '\\')",
            [like] * 6,
        ))
    where, params = _where(clauses)
    total = conn.execute(f"SELECT COUNT(*) FROM alerts{where}", params).fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM alerts" + where +
        " ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, last_seen DESC, alert_id"
        " LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return [_alert_summary(r) for r in rows], total


def get_alert(conn: sqlite3.Connection, alert_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
    if row is None:
        return None
    data = _alert_summary(row)
    data.update({
        "summary": row["summary"],
        "observed": row["observed"],
        "uncertain": row["uncertain"],
        "next_step": row["next_step"],
        "evidence_factors": json.loads(row["evidence_factors"]),
    })
    return data


def get_alert_evidence(conn: sqlite3.Connection, alert_id: str) -> list[dict[str, Any]]:
    """Evidence links for one alert, chronological, each with its stored event."""
    rows = conn.execute(
        "SELECT ae.position, ae.role, ae.reason, e.* FROM alert_events ae "
        "JOIN events e ON e.event_id = ae.event_id WHERE ae.alert_id = ? "
        "ORDER BY ae.position",
        (alert_id,),
    ).fetchall()
    return [
        {"position": r["position"], "role": r["role"], "reason": r["reason"], "event": row_to_event(r)}
        for r in rows
    ]


# ---- Stats --------------------------------------------------------------------
def compute_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    by_priority = {r[0]: r[1] for r in conn.execute("SELECT priority, COUNT(*) FROM alerts GROUP BY priority")}
    by_rule = {r[0]: r[1] for r in conn.execute("SELECT rule_name, COUNT(*) FROM alerts GROUP BY rule_name")}
    by_type = {r[0]: r[1] for r in conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY 2 DESC")}
    by_severity = {r[0]: r[1] for r in conn.execute("SELECT severity, COUNT(*) FROM events GROUP BY severity")}
    last_import = conn.execute("SELECT MAX(imported_at) FROM imports").fetchone()[0]
    return {
        "total_events": total_events,
        "total_alerts": total_alerts,
        "high_priority_alerts": by_priority.get("High", 0),
        "medium_priority_alerts": by_priority.get("Medium", 0),
        "low_priority_alerts": by_priority.get("Low", 0),
        "alerts_by_rule": by_rule,
        "events_by_type": by_type,
        "events_by_severity": by_severity,
        "last_import_at": last_import,
    }
