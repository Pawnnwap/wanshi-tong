import unittest
from unittest.mock import patch

from core.base import Module
from core.pipeline import collect_tasks, merge_results


class ExampleModule(Module):
    name = "example"
    title = "Example"
    prompt_zh = "zh {today_cn}"
    prompt_en = "en {today_en}"


class PipelineTest(unittest.TestCase):
    @patch("core.pipeline.run_parallel", return_value=["中文", "English"])
    def test_collection_and_merge_keep_task_identity(self, run_parallel):
        logs = []
        modules = [ExampleModule()]
        templates = {"today_cn": "今天", "today_en": "today"}

        task_results = collect_tasks(modules, templates, logs.append)
        results = merge_results(modules, task_results, logs.append)

        self.assertEqual(task_results, {"example_zh": "中文", "example_en": "English"})
        self.assertIn("=== 中文搜索结果 ===\n中文", results[0].content)
        self.assertIn("=== English Search Results ===\nEnglish", results[0].content)
        self.assertEqual([task.name for task in run_parallel.call_args.args[0]], ["example_zh", "example_en"])

    def test_duplicate_task_names_fail_before_execution(self):
        with self.assertRaisesRegex(ValueError, "duplicate task names: example_en, example_zh"):
            collect_tasks([ExampleModule(), ExampleModule()], {}, lambda _: None)


if __name__ == "__main__":
    unittest.main()
