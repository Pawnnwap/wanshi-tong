import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from core.base import ModuleResult
from core.context import RunContext
from core.report import cleanup_dates, render_report, save_report


class RunContextTest(unittest.TestCase):
    def test_context_uses_one_timestamp_for_all_dates_and_filename(self):
        context = RunContext(datetime(2026, 7, 14, 23, 59, 58))

        self.assertEqual(context.date_templates["yesterday_cn"], "2026年7月13日")
        self.assertEqual(context.date_templates["today_en"], "July 14, 2026")
        self.assertEqual(context.report_filename, "wanshi_tong_20260714_2359.md")


class ReportTest(unittest.TestCase):
    def test_render_cleanup_and_save_are_separate_report_steps(self):
        context = RunContext(datetime(2026, 7, 14, 10, 5, 0))
        result = ModuleResult(
            name="news",
            title="新闻",
            content="旧闻 | 2026年7月12日\n今日新闻 | 2026年7月14日",
        )

        rendered = render_report([result], "分析引用 2026年7月12日", context)
        cleaned = cleanup_dates(rendered, context.allowed_dates)

        self.assertNotIn("旧闻 | 2026年7月12日", cleaned)
        self.assertIn("今日新闻 | 2026年7月14日", cleaned)
        self.assertIn("分析引用 2026年7月12日", cleaned)

        with tempfile.TemporaryDirectory() as directory:
            path = save_report(cleaned, Path(directory) / context.report_filename)
            self.assertEqual(path.read_text(encoding="utf-8"), cleaned)


if __name__ == "__main__":
    unittest.main()
