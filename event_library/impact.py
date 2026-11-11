"""Event-study path measurement. No network and no trading simulation."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

RUBRIC_VERSION = "impact-v1"
VENUE = "binance-usdm"
INTERVAL = "1m"
ASSETS = ("BTC", "ETH", "SOL")
SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
WINDOWS = (("1h", 60), ("4h", 240), ("24h", 1440), ("7d", 10080))


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def event_instant(event: dict) -> datetime | None:
    if event.get("timeStatus") != "verified_instant":
        return None
    local = datetime.fromisoformat(event["localTime"]).replace(tzinfo=ZoneInfo(event["timeZone"]))
    return local.astimezone(UTC)


def assign_regimes(events: list[dict]) -> dict[str, dict]:
    """Rate environment is the latest stored FOMC target at or before the event.

    The next stored FOMC closes the interval. Without that next statement the
    interval stays open_ended instead of being treated as still in force forever.
    """
    decisions = []
    for event in events:
        if event.get("eventType") != "fomc" or event.get("timeStatus") != "verified_instant":
            continue
        shock = event["shock"]
        decisions.append(
            {
                "id": event["id"],
                "at": event_instant(event),
                "lower": shock["targetLowerPct"],
                "upper": shock["targetUpperPct"],
            }
        )
    decisions.sort(key=lambda row: row["at"])
    assigned = {}
    for event in events:
        at = event_instant(event)
        if at is None:
            assigned[event["id"]] = {"status": "unknown", "reason": "event time is not a verified instant"}
            continue
        prior = [row for row in decisions if row["at"] <= at]
        if not prior:
            assigned[event["id"]] = {"status": "unknown", "reason": "no earlier FOMC statement in this library"}
            continue
        current = prior[-1]
        nxt = next((row for row in decisions if row["at"] > at), None)
        assigned[event["id"]] = {
            "status": "bounded" if nxt else "open_ended",
            "targetLowerPct": current["lower"],
            "targetUpperPct": current["upper"],
            "since": current["at"].isoformat(),
            "until": nxt["at"].isoformat() if nxt else None,
            "sourceEventId": current["id"],
        }
    return assigned


def _minute(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("candle time must be timezone-aware")
    return parsed.astimezone(UTC)


def measure_path(candles: list[dict], event_time: datetime) -> dict:
    """Measure returns from the last 1-minute close at or before the event.

    A horizon ends on the 1-minute close exactly `minutes` after the event.
    Missing minutes make that horizon unavailable. Shorter intact horizons remain.
    High and low excursions use only bars that close after the event.
    """
    if event_time.tzinfo is None:
        raise ValueError("event time must be timezone-aware")
    at = event_time.astimezone(UTC).replace(second=0, microsecond=0)
    ordered = sorted(candles, key=lambda row: row["openTime"])
    by_open = {}
    for row in ordered:
        opened = _minute(row["openTime"])
        if opened in by_open:
            raise ValueError("duplicate candle")
        by_open[opened] = row
    anchor_open = at - timedelta(minutes=1)
    if anchor_open not in by_open:
        return {"status": "unavailable", "error": "missing pre-event minute"}
    anchor = by_open[anchor_open]
    anchor_close = Decimal(anchor["close"])
    if anchor_close <= 0:
        return {"status": "unavailable", "error": "invalid anchor close"}
    windows = {}
    used = [anchor]
    for name, minutes in WINDOWS:
        end_open = at + timedelta(minutes=minutes - 1)
        needed = [anchor_open + timedelta(minutes=step) for step in range(0, minutes + 1)]
        if any(stamp not in by_open for stamp in needed):
            windows[name] = {"status": "unavailable", "error": "gap in minute bars"}
            continue
        span = [by_open[stamp] for stamp in needed]
        endpoint = by_open[end_open]
        end_close = Decimal(endpoint["close"])
        after = span[1:]
        high = max(Decimal(row["high"]) for row in after)
        low = min(Decimal(row["low"]) for row in after)
        windows[name] = {
            "status": "measured",
            "endOpenTime": endpoint["openTime"],
            "endClose": format(end_close, "f"),
            "elapsedMinutes": minutes,
            "returnPct": _pct(end_close, anchor_close),
            "maxUpPct": _pct(high, anchor_close),
            "maxDownPct": _pct(low, anchor_close),
        }
        used.extend(span[1:])
    unique = []
    seen = set()
    for row in used:
        if row["openTime"] not in seen:
            seen.add(row["openTime"])
            unique.append({key: row[key] for key in ("openTime", "open", "high", "low", "close")})
    return {
        "status": "measured" if any(row["status"] == "measured" for row in windows.values()) else "unavailable",
        "anchorOpenTime": anchor["openTime"],
        "anchorClose": format(anchor_close, "f"),
        "staleSeconds": int((at - (anchor_open + timedelta(minutes=1))).total_seconds()),
        "windows": windows,
        "seriesHash": digest(unique),
        "seriesCount": len(unique),
    }


def _pct(price: Decimal, anchor: Decimal) -> str:
    return format(((price / anchor) - 1) * 100, ".6f")
