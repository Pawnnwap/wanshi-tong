import os
import sys
import unittest
from unittest.mock import patch

from core.opencode_client import _run_process_with_idle_progress, run_opencode, run_parallel


class OpenCodeFailureTest(unittest.TestCase):
    def test_process_idle_timeout_resets_on_output(self):
        script = (
            "import json, sys, time\n"
            "for part in ['one', 'two']:\n"
            "    print(json.dumps({'type': 'text', 'part': {'text': part}}), flush=True)\n"
            "    time.sleep(0.2)\n"
        )

        stdout, stderr, returncode = _run_process_with_idle_progress(
            [sys.executable, "-c", script],
            "",
            1,
            "test progress",
            os.environ.copy(),
        )

        self.assertEqual(returncode, 0)
        self.assertEqual(stderr, [])
        self.assertEqual(len(stdout), 2)

    @patch("core.config.load_config", return_value={"opencode": {"model": "agnes/agnes-2.0-flash"}})
    @patch("core.opencode_client._run_single", return_value=("result", True))
    def test_run_opencode_uses_configured_model_by_default(self, run_single, load_config):
        self.assertEqual(run_opencode("prompt", task_name="example"), "result")

        self.assertEqual(run_single.call_args.args[1], "agnes/agnes-2.0-flash")

    @patch("core.opencode_client._run_single", return_value=("", False))
    def test_run_opencode_raises_when_all_models_fail(self, run_single):
        with self.assertRaisesRegex(RuntimeError, "example: all configured models failed"):
            run_opencode("prompt", model="test/model", task_name="example")

        run_single.assert_called_once()

    @patch("core.opencode_client.run_opencode")
    def test_parallel_collection_propagates_task_failures(self, run_single):
        def execute(prompt, model, timeout_s, task_name, max_attempts=0):
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

    @patch("core.opencode_client.run_opencode")
    def test_parallel_collection_passes_task_max_attempts(self, run_single):
        run_single.return_value = "result"
        tasks = [{"name": "macro", "prompt": "one", "max_attempts": 1}]

        self.assertEqual(run_parallel(tasks), ["result"])

        self.assertEqual(run_single.call_args.args[4], 1)


if __name__ == "__main__":
    unittest.main()
