import unittest
from unittest.mock import patch

from analyzers.deep_analyzer import DeepAnalyzer
from core.base import ModuleResult


COMPLETE_ANALYSIS = """## 1. 【核心主题】
核心主题内容足够完整。

## 2. 【传导链】
传导链内容足够完整。

## 3. 【一致与背离】
**一致信号：**
（1）宏观、政策和市场之间互相印证。
（2）资产价格与产业新闻之间互相印证。
**背离/张力：**
（1）资产价格与风险新闻之间存在定价差异。
（2）科技投资与社会风险之间存在时间错位。

## 4. 【风险与机会】
风险与机会内容足够完整。

## 5. 【综合判断】
综合判断内容足够完整。
"""


class DeepAnalyzerTest(unittest.TestCase):
    def test_missing_sections_detects_empty_required_section(self):
        incomplete = COMPLETE_ANALYSIS.replace("综合判断内容足够完整。", "")

        self.assertEqual(DeepAnalyzer._missing_sections(incomplete), ["综合判断"])

    @patch("analyzers.deep_analyzer.run_opencode")
    def test_analyze_retries_when_required_section_is_empty(self, run_opencode):
        incomplete = COMPLETE_ANALYSIS.replace("综合判断内容足够完整。", "")
        run_opencode.side_effect = [incomplete, COMPLETE_ANALYSIS]

        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 2)
        self.assertEqual(run_opencode.call_args.kwargs["task_name"], "deep_analysis_retry")

    @patch("analyzers.deep_analyzer.run_opencode", return_value=COMPLETE_ANALYSIS)
    def test_analyze_does_not_retry_complete_output(self, run_opencode):
        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 1)

    @patch("analyzers.deep_analyzer.run_opencode")
    def test_analyze_retries_when_alignment_section_is_weak(self, run_opencode):
        weak = COMPLETE_ANALYSIS.replace(
            "**一致信号：**\n"
            "（1）宏观、政策和市场之间互相印证。\n"
            "（2）资产价格与产业新闻之间互相印证。\n"
            "**背离/张力：**\n"
            "（1）资产价格与风险新闻之间存在定价差异。\n"
            "（2）科技投资与社会风险之间存在时间错位。",
            "多个信号之间存在一致与背离。",
        )
        run_opencode.side_effect = [weak, COMPLETE_ANALYSIS]

        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 2)

    @patch("analyzers.deep_analyzer.run_opencode")
    def test_analyze_retries_when_divergence_subsection_is_empty(self, run_opencode):
        weak = COMPLETE_ANALYSIS.replace(
            "**一致信号：**\n"
            "（1）宏观、政策和市场之间互相印证。\n"
            "（2）资产价格与产业新闻之间互相印证。\n"
            "**背离/张力：**\n"
            "（1）资产价格与风险新闻之间存在定价差异。\n"
            "（2）科技投资与社会风险之间存在时间错位。",
            "### 一致信号\n\n宏观、政策和市场之间互相印证。\n\n### 背离/张力\n\n",
        )
        run_opencode.side_effect = [weak, COMPLETE_ANALYSIS]

        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 2)

    @patch("analyzers.deep_analyzer.run_opencode")
    def test_analyze_retries_when_alignment_subsection_has_too_few_items(self, run_opencode):
        weak = COMPLETE_ANALYSIS.replace(
            "（1）宏观、政策和市场之间互相印证。\n"
            "（2）资产价格与产业新闻之间互相印证。",
            "（2）资产价格与产业新闻之间互相印证。",
        )
        run_opencode.side_effect = [weak, COMPLETE_ANALYSIS]

        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 2)

    @patch("analyzers.deep_analyzer.run_opencode")
    def test_analyze_final_retries_when_retry_is_still_weak(self, run_opencode):
        weak = COMPLETE_ANALYSIS.replace(
            "（1）资产价格与风险新闻之间存在定价差异。\n"
            "（2）科技投资与社会风险之间存在时间错位。",
            "（2）科技投资与社会风险之间存在时间错位。",
        )
        run_opencode.side_effect = [weak, weak, COMPLETE_ANALYSIS]

        result = DeepAnalyzer().analyze([
            ModuleResult(name="political_news", title="政经", content="内容")
        ])

        self.assertEqual(result, COMPLETE_ANALYSIS)
        self.assertEqual(run_opencode.call_count, 3)
        self.assertEqual(run_opencode.call_args.kwargs["task_name"], "deep_analysis_final_retry")


if __name__ == "__main__":
    unittest.main()
