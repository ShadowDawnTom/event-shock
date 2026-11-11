from event_library.measure import build


def main() -> None:
    rows = build()
    print(f"{len(rows)} events")
    for row in rows:
        btc = (row.get("impacts") or {}).get("BTC") or {}
        windows = btc.get("windows") or {}
        one = (windows.get("1h") or {}).get("returnPct", btc.get("error") or btc.get("status"))
        day = (windows.get("24h") or {}).get("returnPct", "")
        print(f"{row['happenedAt'] or row['timeStatus']:25} {row['id']:20} BTC 1h {one}  24h {day}")


if __name__ == "__main__":
    main()
