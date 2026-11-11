"""Download 120 daily spot candles for a fixed set of large coins."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PRIORITY = [
    ("BTCUSDT", "BTC", "大盘"),
    ("ETHUSDT", "ETH", "大盘"),
    ("SOLUSDT", "SOL", "大盘"),
    ("BNBUSDT", "BNB", "大盘"),
    ("XRPUSDT", "XRP", "大盘"),
    ("DOGEUSDT", "DOGE", "大盘"),
    ("ADAUSDT", "ADA", "大盘"),
    ("AVAXUSDT", "AVAX", "大盘"),
    ("LINKUSDT", "LINK", "大盘"),
    ("TRXUSDT", "TRX", "大盘"),
    ("UNIUSDT", "UNI", "DeFi"),
    ("AAVEUSDT", "AAVE", "DeFi"),
    ("MKRUSDT", "MKR", "DeFi"),
    ("SKYUSDT", "SKY", "DeFi"),
    ("LDOUSDT", "LDO", "DeFi"),
    ("CRVUSDT", "CRV", "DeFi"),
    ("PENDLEUSDT", "PENDLE", "DeFi"),
    ("JUPUSDT", "JUP", "DeFi"),
    ("SNXUSDT", "SNX", "DeFi"),
    ("SUIUSDT", "SUI", "主流"),
    ("APTUSDT", "APT", "主流"),
    ("NEARUSDT", "NEAR", "主流"),
    ("TONUSDT", "TON", "主流"),
    ("DOTUSDT", "DOT", "主流"),
    ("LTCUSDT", "LTC", "主流"),
    ("ARBUSDT", "ARB", "主流"),
    ("OPUSDT", "OP", "主流"),
    ("INJUSDT", "INJ", "主流"),
    ("ATOMUSDT", "ATOM", "主流"),
    ("BCHUSDT", "BCH", "主流"),
    ("FILUSDT", "FIL", "主流"),
    ("SEIUSDT", "SEI", "主流"),
    ("HBARUSDT", "HBAR", "主流"),
    ("RUNEUSDT", "RUNE", "DeFi"),
    ("ENAUSDT", "ENA", "DeFi"),
]
OUT = Path(__file__).resolve().parent / "data" / "spot_daily_30.json"


def get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "event-library/kline-v1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    info = get_json("https://api.binance.com/api/v3/exchangeInfo")
    trading = {
        row["symbol"]
        for row in info["symbols"]
        if row["status"] == "TRADING" and row["quoteAsset"] == "USDT"
    }
    chosen = []
    seen = set()
    for symbol, name, group in PRIORITY:
        if symbol not in trading or name in seen:
            continue
        chosen.append((symbol, name, group))
        seen.add(name)
        if len(chosen) == 30:
            break
    if len(chosen) < 30:
        raise SystemExit(f"only found {len(chosen)} symbols")
    coins = []
    for symbol, name, group in chosen:
        raw = get_json(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=120")
        bars = []
        for row in raw:
            opened = datetime.fromtimestamp(int(row[0]) / 1000, UTC).date().isoformat()
            bars.append([opened, float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])])
        first, last = bars[0][1], bars[-1][4]
        coins.append(
            {
                "symbol": symbol,
                "name": name,
                "group": group,
                "changePct": (last / first - 1) * 100,
                "last": last,
                "bars": bars,
            }
        )
        print(name, len(bars), round(coins[-1]["changePct"], 2))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"venue": "binance-spot", "interval": "1d", "coins": coins}, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, "coins", len(coins))


if __name__ == "__main__":
    main()
