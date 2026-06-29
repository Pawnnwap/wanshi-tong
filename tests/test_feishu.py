import unittest
from datetime import date
from unittest.mock import patch

from reporters.feishu import _send_card_with_retry, cleanup_dates


class CleanupDatesTest(unittest.TestCase):
    def setUp(self):
        self.allowed_dates = (date(2026, 6, 28), date(2026, 6, 29))

    def test_keeps_dates_in_collection_window(self):
        content = (
            "中文新闻 | 2026年6月28日\n"
            "另一条新闻 | 6月29日\n"
            "ISO news | 2026-06-29"
        )

        self.assertEqual(
            cleanup_dates(content, self.allowed_dates),
            content,
        )

    def test_removes_dates_outside_collection_window(self):
        content = (
            "保留 | 2026年6月29日\n"
            "删除 | 2026年6月6日\n"
            "也删除 | 2026-06-27"
        )

        self.assertEqual(
            cleanup_dates(content, self.allowed_dates),
            "保留 | 2026年6月29日",
        )

    def test_handles_month_boundary(self):
        allowed_dates = (date(2026, 6, 30), date(2026, 7, 1))
        content = (
            "昨天 | 6月30日\n"
            "今天 | 2026年7月1日\n"
            "旧闻 | 6月29日"
        )

        self.assertEqual(
            cleanup_dates(content, allowed_dates),
            "昨天 | 6月30日\n今天 | 2026年7月1日",
        )

    def test_collapses_blank_lines_left_by_removed_items(self):
        content = (
            "## 标题\n\n"
            "旧闻 | 2026年6月6日\n\n"
            "新闻 | 2026年6月29日"
        )

        self.assertEqual(
            cleanup_dates(content, self.allowed_dates),
            "## 标题\n\n新闻 | 2026年6月29日",
        )


class SendCardRetryTest(unittest.TestCase):
    @patch("reporters.feishu.time.sleep")
    @patch("reporters.feishu._send_card")
    def test_retries_with_exponential_backoff(self, send_card, sleep):
        send_card.side_effect = [
            RuntimeError("temporary"),
            RuntimeError("temporary"),
            {"code": 0},
        ]

        result = _send_card_with_retry(
            "https://example.invalid",
            "",
            "title",
            "body",
            max_attempts=3,
            retry_delay_s=2,
        )

        self.assertEqual(result, {"code": 0})
        self.assertEqual(send_card.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])

    @patch("reporters.feishu.time.sleep")
    @patch("reporters.feishu._send_card")
    def test_raises_after_last_attempt(self, send_card, sleep):
        send_card.side_effect = RuntimeError("permanent")

        with self.assertRaisesRegex(RuntimeError, "permanent"):
            _send_card_with_retry(
                "https://example.invalid",
                "",
                "title",
                "body",
                max_attempts=3,
                retry_delay_s=2,
            )

        self.assertEqual(send_card.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
