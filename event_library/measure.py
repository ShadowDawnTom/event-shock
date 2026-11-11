"""Fetch public Binance USD-M 1-minute bars and store event paths."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from event_library.impact import ASSETS, INTERVAL, SYMBOLS, VENUE, WINDOWS, assign_regimes, event_instant, measure_path
from event_library.store import DB_PATH, catalog, connect, load_seed, save_impact, upsert_event

CACHE = Path(__file__).resolve().parent / "data" / "cache"
MAX_WINDOW = max(minutes for _name, minutes in WINDOWS)


def fetch_klines(symbol: str, start: datetime, end: datetime) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / f"{symbol}_{int(start.timestamp())}_{int(end.timestamp())}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    rows: dict[int, dict] = {}
    cursor = int(start.timestamp() * 1000)
    stop = int(end.timestamp() * 1000)
    while cursor < stop:
        params = f"symbol={symbol}&interval=1m&startTime={cursor}&endTime={stop - 1}&limit=1500"
        url = "https://fapi.binance.com/fapi/v1/klines?" + params
        batch = _get_json(url)
        if not isinstance(batch, list) or not batch:
            break
        for raw in batch:
            opened = int(raw[0])
            if cursor <= opened < stop:
                rows[opened] = {
                    "openTime": datetime.fromtimestamp(opened / 1000, UTC).isoformat(),
                    "open": raw[1],
                    "high": raw[2],
                    "low": raw[3],
                    "close": raw[4],
                }
        nxt = int(batch[-1][0]) + 60_000
        if nxt <= cursor:
            raise RuntimeError(f"{symbol} pagination did not advance")
        cursor = nxt
        if len(batch) < 1500:
            break
    candles = [rows[stamp] for stamp in sorted(rows)]
    key.write_text(json.dumps(candles), encoding="utf-8")
    return candles


def _get_json(url: str):
    last_error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "event-library/impact-v1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # network and HTTP errors stay retryable
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"kline request failed: {last_error}")


def build(db_path=DB_PATH) -> list[dict]:
    seed = load_seed()
    events = seed["events"]
    regimes = assign_regimes(events)
    db = connect(db_path)
    try:
        for event in events:
            instant = event_instant(event)
            upsert_event(db, event, instant.isoformat() if instant else None)
            db.execute(
                "INSERT INTO regimes VALUES (?,?) ON CONFLICT(event_id) DO UPDATE SET regime_json=excluded.regime_json",
                (event["id"], json.dumps(regimes[event["id"]], ensure_ascii=False, sort_keys=True)),
            )
            if instant is None:
                for asset in ASSETS:
                    save_impact(db, event["id"], asset, VENUE, INTERVAL, {"status": "not_measured", "error": "time is not a verified instant"})
                continue
            start = instant - timedelta(minutes=2)
            end = instant + timedelta(minutes=MAX_WINDOW + 1)
            for asset in ASSETS:
                try:
                    candles = fetch_klines(SYMBOLS[asset], start, end)
                    result = measure_path(candles, instant)
                except Exception as exc:
                    result = {"status": "unavailable", "error": str(exc)}
                save_impact(db, event["id"], asset, VENUE, INTERVAL, result)
        db.commit()
        rows = catalog(db)
    finally:
        db.close()
    out = Path(db_path).with_name("summary.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows
