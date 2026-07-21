import unittest
from unittest.mock import patch

from core.base import ModuleResult
from filters.importance_filter import ImportanceFilter


class ImportanceFilterTest(unittest.TestCase):
    @patch("filters.importance_filter.run_opencode", return_value="不应被调用")
    def test_macro_data_authoritative_results_skip_filtering(self, run_opencode):
        module_result = ModuleResult(
            name="macro_data",
            title="宏观",
            content="CPI (同比) CPI (YoY) | 1.00% | 2026-06-01 | East Money",
            authoritative=True,
        )

        result = ImportanceFilter().filter(module_result)

        run_opencode.assert_not_called()
        self.assertIs(result, module_result)

    @patch("filters.importance_filter.run_opencode", return_value="不应被调用")
    def test_authoritative_results_skip_filtering(self, run_opencode):
        module_result = ModuleResult(
            name="asset_prices",
            title="资产",
            content="上证指数 | 3864 | +1.79% | 2026-07-21",
            authoritative=True,
        )

        result = ImportanceFilter().filter(module_result)

        run_opencode.assert_not_called()
        self.assertIs(result, module_result)

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
