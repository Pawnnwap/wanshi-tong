import unittest
from unittest.mock import patch

from core.opencode_client import run_opencode, run_parallel


class OpenCodeFailureTest(unittest.TestCase):
    @patch("core.opencode_client._run_single", return_value=("", False))
    def test_run_opencode_raises_when_all_models_fail(self, run_single):
        with self.assertRaisesRegex(RuntimeError, "example: all configured models failed"):
            run_opencode("prompt", model="test/model", task_name="example")

        run_single.assert_called_once()

    @patch("core.opencode_client.run_opencode")
    def test_parallel_collection_propagates_task_failures(self, run_single):
        def execute(prompt, model, timeout_s, task_name):
            if task_name == "broken":
                raise RuntimeError("provider unavailable")
            return "result"

        run_single.side_effect = execute
        tasks = [
            {"name": "working", "prompt": "one"},
            {"name": "broken", "prompt": "two"},
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            "parallel collection failed: broken: provider unavailable",
        ):
            run_parallel(tasks)


if __name__ == "__main__":
    unittest.main()
