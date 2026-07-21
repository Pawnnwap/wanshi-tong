import unittest
from datetime import date, timedelta

from modules.market_data import (
    Asset,
    S,
    _metrics_from_series,
    _percentile_rank,
    render_table,
)


def _asset() -> Asset:
    return Asset(key="x", zh="测试", en="Test", sources=(S("index_em", "X"),))


def _series(closes, end=date(2026, 7, 21)):
    """Build ascending [(date, close)] ending at `end`, one calendar day apart."""
    start = end - timedelta(days=len(closes) - 1)
    return [(start + timedelta(days=i), float(c)) for i, c in enumerate(closes)]


class PercentileRankTest(unittest.TestCase):
    def test_top_and_bottom_of_range(self):
        values = [10, 20, 30, 40, 50]
        self.assertEqual(_percentile_rank(values, 50), 100.0)
        self.assertEqual(_percentile_rank(values, 10), 20.0)

    def test_empty_is_nan(self):
        import math

        self.assertTrue(math.isnan(_percentile_rank([], 5)))


class MetricsTest(unittest.TestCase):
    def test_change_and_change_pct(self):
        metrics = _metrics_from_series(_asset(), _series([100, 110]))
        self.assertEqual(metrics.last, 110)
        self.assertEqual(metrics.prev, 100)
        self.assertEqual(metrics.change, 10)
        self.assertAlmostEqual(metrics.change_pct, 10.0)

    def test_percentile_windows(self):
        # 260 ascending closes: the latest is the highest in every window.
        metrics = _metrics_from_series(_asset(), _series(list(range(1, 261))))
        self.assertEqual(metrics.pct_20d, 100.0)
        self.assertEqual(metrics.pct_60d, 100.0)
        self.assertEqual(metrics.pct_1y, 100.0)
        self.assertEqual(metrics.high_1y, 260.0)

    def test_one_year_window_excludes_older_points(self):
        # Two years of data; the 1-year window must only see ~365 days back.
        closes = list(range(1, 731))
        metrics = _metrics_from_series(_asset(), _series(closes))
        self.assertLessEqual(metrics.points_1y, 366)
        self.assertGreater(metrics.points_1y, 360)

    def test_short_history_leaves_windows_blank(self):
        # Too few points for any window -> all percentiles blank, but the
        # latest price and daily change still render.
        metrics = _metrics_from_series(_asset(), _series([1, 2, 3]))
        self.assertEqual(metrics.last, 3)
        self.assertEqual(metrics.change, 1)
        self.assertIsNone(metrics.pct_20d)
        self.assertIsNone(metrics.pct_60d)
        self.assertIsNone(metrics.pct_1y)

    def test_single_point_spot_fallback_has_no_percentiles(self):
        # A spot-only fallback (one point) must not report a bogus 100% rank.
        metrics = _metrics_from_series(_asset(), _series([42]))
        self.assertEqual(metrics.last, 42)
        self.assertIsNone(metrics.change)
        self.assertIsNone(metrics.pct_1y)
        self.assertIsNone(metrics.low_1y)

    def test_stale_data_is_rejected(self):
        old_end = date.today() - timedelta(days=40)
        metrics = _metrics_from_series(_asset(), _series([1, 2, 3], end=old_end))
        self.assertIsNone(metrics.last)
        self.assertIn("stale", metrics.error)

    def test_empty_series_errors(self):
        metrics = _metrics_from_series(_asset(), [])
        self.assertEqual(metrics.error, "no data")


class RenderTest(unittest.TestCase):
    def test_render_includes_header_and_error_rows(self):
        good = _metrics_from_series(_asset(), _series([100, 110]))
        bad = _metrics_from_series(
            Asset(key="y", zh="坏", en="Bad", sources=(S("forex_em", "Y"),)), []
        )
        table = render_table([good, bad])
        self.assertIn("| 资产 Asset |", table)
        self.assertIn("[no data]", table)
        self.assertIn("Coverage 1/2", table)


if __name__ == "__main__":
    unittest.main()
