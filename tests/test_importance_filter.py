import unittest
from unittest.mock import patch

from core.base import ModuleResult
from filters.importance_filter import ImportanceFilter


class ImportanceFilterTest(unittest.TestCase):
    @patch("filters.importance_filter.run_opencode", return_value="整理后内容")
    def test_asset_prices_use_structured_consolidation_prompt(self, run_opencode):
        module_result = ModuleResult(
            name="asset_prices",
            title="资产",
            content="上证 | 3000 | +1% | 2026-07-14",
        )

        result = ImportanceFilter().filter(module_result)

        prompt = run_opencode.call_args.args[0]
        self.assertIn("不要按新闻重要性丢弃市场价格", prompt)
        self.assertIn("名称 | 价格 | 涨跌幅 | 日期 | 来源", prompt)
        self.assertNotIn("若无保留项，输出：本次搜索未发现重大新闻", prompt)
        self.assertEqual(result.content, "整理后内容")

    @patch("filters.importance_filter.run_opencode", return_value="筛选后内容")
    def test_news_modules_use_importance_prompt(self, run_opencode):
        module_result = ModuleResult(
            name="political_news",
            title="政治",
            content="news",
        )

        result = ImportanceFilter().filter(module_result)

        prompt = run_opencode.call_args.args[0]
        self.assertIn("筛选高重要性新闻", prompt)
        self.assertIn("本次搜索未发现重大新闻", prompt)
        self.assertEqual(result.content, "筛选后内容")


if __name__ == "__main__":
    unittest.main()
