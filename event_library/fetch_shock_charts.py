"""Download the minutes around each verified print and pack a shock chart.

Twelve USD-M perpetuals. The path math is the same as impact-v1: the anchor
is the last completed 1-minute close at or before the release, and a window
with any missing minute is left unmeasured.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from event_library.impact import assign_regimes, event_instant, measure_path
from event_library.store import load_seed

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "cache_shock"
OUT = ROOT / "data" / "shock_charts.json"
ET = ZoneInfo("America/New_York")

COINS = [
    ("BTC", "比特币", "BTCUSDT"),
    ("ETH", "以太坊", "ETHUSDT"),
    ("SOL", "Solana", "SOLUSDT"),
    ("HYPE", "Hyperliquid", "HYPEUSDT"),
    ("AAVE", "AAVE", "AAVEUSDT"),
    ("UNI", "UNI", "UNIUSDT"),
    ("ZEC", "ZEC", "ZECUSDT"),
    ("BNB", "BNB", "BNBUSDT"),
    ("XRP", "XRP", "XRPUSDT"),
    ("DOGE", "DOGE", "DOGEUSDT"),
    ("LINK", "LINK", "LINKUSDT"),
    ("ADA", "ADA", "ADAUSDT"),
]

SHORT = {
    "fomc-2024-09-18": "9/18 降50bp",
    "cpi-2024-09": "10/10 CPI",
    "nfp-2024-10": "11/1 非农",
    "fomc-2024-11-07": "11/7 降25bp",
    "cpi-2024-10": "11/13 CPI",
    "nfp-2024-11": "12/6 非农",
    "cpi-2024-11": "12/11 CPI",
    "fomc-2024-12-18": "12/18 降25bp",
    "cpi-2024-12": "1/15 CPI",
}

SOURCE = {
    "fomc": "美联储",
    "cpi": "美国劳工统计局",
    "employment": "美国劳工统计局",
}

PRE_CHOICES = (30, 15, 0)
HORIZONS = (("1h", 60), ("4h", 240), ("24h", 1440))


def _get_json(url: str):
    last_error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "event-library/shock-chart-v1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(str(last_error))


def trading_symbols() -> set[str]:
    info = _get_json("https://fapi.binance.com/fapi/v1/exchangeInfo")
    return {row["symbol"] for row in info["symbols"] if row.get("status") == "TRADING"}


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
        batch = _get_json("https://fapi.binance.com/fapi/v1/klines?" + params)
        if isinstance(batch, dict):
            raise RuntimeError(batch.get("msg") or "kline request rejected")
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
                    "volume": raw[5],
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


def _index(candles: list[dict]) -> dict[datetime, dict]:
    out = {}
    for row in candles:
        opened = datetime.fromisoformat(row["openTime"]).astimezone(UTC).replace(second=0, microsecond=0)
        out[opened] = row
    return out


def _slice(by_open: dict[datetime, dict], start: datetime, end: datetime) -> list[dict] | None:
    rows = []
    stamp = start
    while stamp <= end:
        row = by_open.get(stamp)
        if row is None:
            return None
        rows.append(row)
        stamp += timedelta(minutes=1)
    return rows


def qprice(value: str) -> float:
    number = Decimal(value)
    if number >= 100:
        places = Decimal("0.01")
    elif number >= 1:
        places = Decimal("0.0001")
    elif number >= Decimal("0.01"):
        places = Decimal("0.000001")
    else:
        places = Decimal("0.00000001")
    return float(number.quantize(places))


def qvol(value: str) -> float:
    number = Decimal(value)
    places = Decimal("0.01") if number >= 1 else Decimal("0.0001")
    return float(number.quantize(places))


def pack_bars(rows: list[dict]) -> list[list[float]]:
    return [
        [qprice(row["open"]), qprice(row["high"]), qprice(row["low"]), qprice(row["close"]), qvol(row["volume"])]
        for row in rows
    ]


def pack_15m(rows: list[dict]) -> list[list[float]] | None:
    if len(rows) % 15 != 0:
        return None
    packed = []
    for offset in range(0, len(rows), 15):
        chunk = rows[offset : offset + 15]
        high = max(Decimal(row["high"]) for row in chunk)
        low = min(Decimal(row["low"]) for row in chunk)
        volume = sum(Decimal(row["volume"]) for row in chunk)
        packed.append(
            [
                qprice(chunk[0]["open"]),
                qprice(format(high, "f")),
                qprice(format(low, "f")),
                qprice(chunk[-1]["close"]),
                qvol(format(volume, "f")),
            ]
        )
    return packed


def longest_pre(by_open: dict[datetime, dict], at: datetime, end: datetime) -> tuple[int, list[dict]] | None:
    for pre in PRE_CHOICES:
        rows = _slice(by_open, at - timedelta(minutes=pre), end)
        if rows is not None:
            return pre, rows
    return None


def shock_line(event: dict) -> str:
    shock = event["shock"]
    if event["eventType"] == "fomc":
        change = int(shock["changeBp"])
        verb = "下调" if change < 0 else "上调" if change > 0 else "维持"
        lower = f"{Decimal(str(shock['targetLowerPct'])):.2f}"
        upper = f"{Decimal(str(shock['targetUpperPct'])):.2f}"
        moved = f" {abs(change)}bp" if change else ""
        return f"联邦基金利率目标区间{verb}{moved}，至 {lower}%–{upper}%。"
    if event["eventType"] == "cpi":
        return (
            f"CPI 季调环比 {shock['actualMomSaPct']:+.1f}%，此前 {shock['previousMomSaPct']:+.1f}%；"
            f"同比 {shock['actualYoyNsaPct']:+.1f}%。核心环比 {shock['coreMomSaPct']:+.1f}%。"
        )
    payroll = Decimal(shock["actualPayrollChange"]) / Decimal(10000)
    wan = format(payroll.normalize(), "f")
    return f"非农就业 {wan} 万，失业率 {shock['unemploymentRatePct']:.1f}%。"


def regime_line(regime: dict) -> str:
    if regime.get("status") not in {"bounded", "open_ended"}:
        return "这次公布之前，库里没有已收录的 FOMC 声明。"
    lower = f"{Decimal(str(regime['targetLowerPct'])):.2f}"
    upper = f"{Decimal(str(regime['targetUpperPct'])):.2f}"
    base = f"当时联邦基金利率区间 {lower}%–{upper}%"
    if regime["status"] == "open_ended":
        return base + "。下一次决议还没收录，区间不做封口。"
    until = datetime.fromisoformat(regime["until"]).astimezone(ET)
    return base + f"，封口至 {until.month}/{until.day}。"


def local_label(event: dict) -> str:
    stamp = datetime.fromisoformat(event["localTime"])
    return stamp.strftime("%Y-%m-%d %H:%M") + " 美东"


def pct_points(price: Decimal, anchor: Decimal) -> float:
    return float((((price / anchor) - 1) * 100).quantize(Decimal("0.000001")))


def window_stat(row: dict) -> dict:
    return {
        "ret": float(row["returnPct"]),
        "up": float(row["maxUpPct"]),
        "dn": float(row["maxDownPct"]),
        "end": float(row["endClose"]),
    }


def extreme_times(by_open: dict[datetime, dict], at: datetime, minutes: int) -> dict:
    """First minute the high and the low print. Clock starts at the release."""
    low = None
    high = None
    t_dn = None
    t_up = None
    for step in range(minutes):
        row = by_open.get(at + timedelta(minutes=step))
        if row is None:
            return {}
        lo = Decimal(row["low"])
        hi = Decimal(row["high"])
        if low is None or lo < low:
            low = lo
            t_dn = step + 1
        if high is None or hi > high:
            high = hi
            t_up = step + 1
    return {"tDn": t_dn, "tUp": t_up}


def impulse_fields(by_open: dict[datetime, dict], at: datetime, anchor: Decimal) -> dict:
    """What a trader reads before the horizon return: drift in, first minutes, volume."""
    out = {}
    before = by_open.get(at - timedelta(minutes=31))
    if before is not None and Decimal(before["close"]) > 0:
        out["pre"] = pct_points(anchor, Decimal(before["close"]))
    first = by_open.get(at)
    if first is not None:
        out["r1"] = pct_points(Decimal(first["close"]), anchor)
    fifth = by_open.get(at + timedelta(minutes=4))
    if fifth is not None:
        out["r5"] = pct_points(Decimal(fifth["close"]), anchor)
    pre_volume = Decimal(0)
    post_volume = Decimal(0)
    pre_complete = True
    for step in range(1, 31):
        row = by_open.get(at - timedelta(minutes=step))
        if row is None:
            pre_complete = False
            break
        pre_volume += Decimal(row["volume"])
    post_complete = True
    for step in range(5):
        row = by_open.get(at + timedelta(minutes=step))
        if row is None:
            post_complete = False
            break
        post_volume += Decimal(row["volume"])
    if pre_complete and post_complete and pre_volume > 0:
        baseline = pre_volume / Decimal(30) * Decimal(5)
        out["vol"] = float((post_volume / baseline).quantize(Decimal("0.01")))
    return out


def series_for(candles: list[dict], at: datetime) -> dict:
    measured = measure_path(candles, at)
    if measured.get("status") != "measured":
        return {"error": "公布前后的分钟不连续，这个币这次没有路径。"}
    by_open = _index(candles)
    anchor = Decimal(measured["anchorClose"])
    windows = {}
    for name, minutes in HORIZONS:
        row = measured["windows"].get(name) or {}
        if row.get("status") == "measured":
            windows[name] = window_stat(row)
            windows[name].update(extreme_times(by_open, at, minutes))
    packed: dict = {"anchor": float(anchor), "w": windows, **impulse_fields(by_open, at, anchor)}
    if "4h" in windows or "1h" in windows:
        end_minute = 239 if "4h" in windows else 59
        found = longest_pre(by_open, at, at + timedelta(minutes=end_minute))
        if found is not None:
            pre, rows = found
            packed["m1"] = {"pre": pre, "bars": pack_bars(rows)}
    if "24h" in windows:
        found = longest_pre(by_open, at, at + timedelta(minutes=1439))
        if found is not None:
            pre, rows = found
            bars = pack_15m(rows)
            if bars is not None:
                packed["m15"] = {"pre": pre, "bars": bars}
    return packed


def build_pack() -> dict:
    seed = load_seed()
    events = seed["events"]
    regimes = assign_regimes(events)
    listed = trading_symbols()
    pack_events = []
    for event in events:
        at = event_instant(event)
        if at is None:
            continue
        at = at.replace(second=0, microsecond=0)
        start = at - timedelta(minutes=31)
        end = at + timedelta(minutes=1440)
        series = {}
        for coin_id, _name, symbol in COINS:
            if symbol not in listed:
                series[coin_id] = {"error": f"Binance USD-M 没有 {symbol}。"}
                print(f"{event['id']} {symbol} not listed")
                continue
            try:
                candles = fetch_klines(symbol, start, end)
            except Exception as exc:
                series[coin_id] = {"error": f"K 线没有取到：{exc}"}
                print(f"{event['id']} {symbol} ERROR {exc}")
                continue
            if not candles:
                series[coin_id] = {"error": "这个时刻还没有这根永续的分钟 K 线。"}
                print(f"{event['id']} {symbol} empty")
                continue
            series[coin_id] = series_for(candles, at)
            windows = series[coin_id].get("w") or {}
            one = windows.get("1h", {}).get("ret")
            print(f"{event['id']} {symbol} 1h {one}")
        pack_events.append(
            {
                "id": event["id"],
                "short": SHORT[event["id"]],
                "title": event["title"],
                "local": local_label(event),
                "utc": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": SOURCE[event["eventType"]],
                "url": event["sourceUrl"],
                "shock": shock_line(event),
                "detail": event["whatHappened"],
                "regime": regime_line(regimes[event["id"]]),
                "series": series,
            }
        )
    return {
        "coins": [{"id": coin_id, "name": name, "symbol": symbol} for coin_id, name, symbol in COINS],
        "events": pack_events,
    }


def check_against_library(pack: dict) -> None:
    summary_path = ROOT / "data" / "summary.json"
    if not summary_path.exists():
        return
    summary = {row["id"]: row for row in json.loads(summary_path.read_text(encoding="utf-8"))}
    mismatches = 0
    for event in pack["events"]:
        stored = summary.get(event["id"], {}).get("impacts") or {}
        for asset in ("BTC", "ETH", "SOL"):
            fresh = (event["series"].get(asset) or {}).get("w") or {}
            old = (stored.get(asset) or {}).get("windows") or {}
            for horizon in ("1h", "4h", "24h"):
                if horizon not in fresh or (old.get(horizon) or {}).get("status") != "measured":
                    continue
                left = Decimal(str(fresh[horizon]["ret"])).quantize(Decimal("0.000001"))
                right = Decimal(old[horizon]["returnPct"]).quantize(Decimal("0.000001"))
                if left != right:
                    mismatches += 1
                    print(f"DIFF {event['id']} {asset} {horizon} fresh {left} library {right}")
    print(f"library mismatches {mismatches}")


def main() -> None:
    pack = build_pack()
    OUT.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} {OUT.stat().st_size}")
    check_against_library(pack)


if __name__ == "__main__":
    main()
