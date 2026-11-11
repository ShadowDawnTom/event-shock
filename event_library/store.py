"""SQLite ledger for curated events and measured price paths."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from event_library.impact import RUBRIC_VERSION, canonical, digest

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "events.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  happened_at TEXT,
  time_status TEXT NOT NULL,
  anchor_kind TEXT NOT NULL,
  what_happened TEXT NOT NULL,
  source_url TEXT NOT NULL,
  shock_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  rubric_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS regimes (
  event_id TEXT PRIMARY KEY REFERENCES events(id),
  regime_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS impacts (
  event_id TEXT NOT NULL REFERENCES events(id),
  asset TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  detail_json TEXT,
  venue TEXT NOT NULL,
  interval TEXT NOT NULL,
  measured_at TEXT NOT NULL,
  rubric_version TEXT NOT NULL,
  PRIMARY KEY (event_id, asset, rubric_version)
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def load_seed(path: Path | None = None) -> dict:
    return json.loads((path or (ROOT / "events.json")).read_text(encoding="utf-8"))


def upsert_event(db: sqlite3.Connection, event: dict, happened_at: str | None) -> None:
    payload = canonical(event)
    db.execute(
        """INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             event_type=excluded.event_type, title=excluded.title, happened_at=excluded.happened_at,
             time_status=excluded.time_status, anchor_kind=excluded.anchor_kind,
             what_happened=excluded.what_happened, source_url=excluded.source_url,
             shock_json=excluded.shock_json, payload_json=excluded.payload_json,
             content_hash=excluded.content_hash, rubric_version=excluded.rubric_version""",
        (
            event["id"],
            event["eventType"],
            event["title"],
            happened_at,
            event["timeStatus"],
            event["anchorKind"],
            event["whatHappened"],
            event["sourceUrl"],
            json.dumps(event["shock"], ensure_ascii=False, sort_keys=True),
            payload,
            digest(event),
            RUBRIC_VERSION,
        ),
    )


def save_impact(db: sqlite3.Connection, event_id: str, asset: str, venue: str, interval: str, result: dict) -> None:
    db.execute(
        """INSERT INTO impacts VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(event_id, asset, rubric_version) DO UPDATE SET
             status=excluded.status, error=excluded.error, detail_json=excluded.detail_json,
             venue=excluded.venue, interval=excluded.interval, measured_at=excluded.measured_at""",
        (
            event_id,
            asset,
            result.get("status", "unavailable"),
            result.get("error"),
            json.dumps(result, ensure_ascii=False, sort_keys=True),
            venue,
            interval,
            datetime.now(UTC).isoformat(),
            RUBRIC_VERSION,
        ),
    )


def catalog(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """SELECT e.*, r.regime_json,
                  (SELECT json_group_object(i.asset, json(i.detail_json)) FROM impacts i
                   WHERE i.event_id=e.id AND i.rubric_version=e.rubric_version) AS impacts_json
           FROM events e LEFT JOIN regimes r ON r.event_id=e.id
           ORDER BY COALESCE(e.happened_at, e.id)"""
    ).fetchall()
    catalog_rows = []
    for row in rows:
        catalog_rows.append(
            {
                "id": row["id"],
                "eventType": row["event_type"],
                "title": row["title"],
                "happenedAt": row["happened_at"],
                "timeStatus": row["time_status"],
                "whatHappened": row["what_happened"],
                "sourceUrl": row["source_url"],
                "shock": json.loads(row["shock_json"]),
                "contentHash": row["content_hash"],
                "regime": json.loads(row["regime_json"]) if row["regime_json"] else None,
                "impacts": json.loads(row["impacts_json"]) if row["impacts_json"] else {},
            }
        )
    return catalog_rows
