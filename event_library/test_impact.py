import unittest
from datetime import UTC, datetime, timedelta

from event_library.impact import assign_regimes, event_instant, measure_path


def _bar(open_at: datetime, close: str, high: str | None = None, low: str | None = None) -> dict:
    return {
        "openTime": open_at.isoformat(),
        "open": close,
        "high": high or close,
        "low": low or close,
        "close": close,
    }


class ImpactTests(unittest.TestCase):
    def test_new_york_release_converts_across_daylight_saving(self):
        october = event_instant({"timeStatus": "verified_instant", "localTime": "2024-10-10T08:30:00", "timeZone": "America/New_York"})
        december = event_instant({"timeStatus": "verified_instant", "localTime": "2024-12-11T08:30:00", "timeZone": "America/New_York"})
        self.assertEqual(october.isoformat(), "2024-10-10T12:30:00+00:00")
        self.assertEqual(december.isoformat(), "2024-12-11T13:30:00+00:00")

    def test_date_only_event_has_no_instant(self):
        self.assertIsNone(event_instant({"timeStatus": "date_only", "localTime": "2024-01-10T00:00:00", "timeZone": "America/New_York"}))

    def test_return_uses_pre_event_close_and_exact_horizon(self):
        at = datetime(2024, 10, 10, 12, 30, tzinfo=UTC)
        candles = []
        for step in range(-1, 61):
            opened = at + timedelta(minutes=step - 1)
            price = 100 + step
            candles.append(_bar(opened, str(price), high=str(price + 2), low=str(price - 3)))
        result = measure_path(candles, at)
        self.assertEqual(result["anchorClose"], "100")
        self.assertEqual(result["windows"]["1h"]["endClose"], "160")
        self.assertEqual(result["windows"]["1h"]["returnPct"], "60.000000")
        self.assertEqual(result["windows"]["4h"]["status"], "unavailable")
        self.assertTrue(result["seriesHash"])

    def test_gap_does_not_invent_a_shorter_window_price(self):
        at = datetime(2024, 10, 10, 12, 30, tzinfo=UTC)
        candles = [_bar(at - timedelta(minutes=1), "100"), _bar(at, "110")]
        result = measure_path(candles, at)
        self.assertEqual(result["windows"]["1h"]["status"], "unavailable")

    def test_regime_stops_at_the_next_stored_decision(self):
        events = [
            {"id": "a", "eventType": "fomc", "timeStatus": "verified_instant", "localTime": "2024-09-18T14:00:00", "timeZone": "America/New_York", "shock": {"targetLowerPct": 4.75, "targetUpperPct": 5}},
            {"id": "b", "eventType": "cpi", "timeStatus": "verified_instant", "localTime": "2024-10-10T08:30:00", "timeZone": "America/New_York", "shock": {}},
            {"id": "c", "eventType": "fomc", "timeStatus": "verified_instant", "localTime": "2024-11-07T14:00:00", "timeZone": "America/New_York", "shock": {"targetLowerPct": 4.5, "targetUpperPct": 4.75}},
            {"id": "d", "eventType": "etf_decision", "timeStatus": "date_only", "localTime": "2024-01-10T00:00:00", "timeZone": "America/New_York", "shock": {}},
        ]
        regimes = assign_regimes(events)
        self.assertEqual(regimes["b"]["status"], "bounded")
        self.assertEqual(regimes["b"]["targetUpperPct"], 5)
        self.assertEqual(regimes["b"]["until"], "2024-11-07T19:00:00+00:00")
        self.assertEqual(regimes["c"]["status"], "open_ended")
        self.assertEqual(regimes["d"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
