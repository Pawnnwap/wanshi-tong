import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

from core.base import Task
from core.opencode_client import _run_process_with_idle_progress, run_opencode, run_parallel
from core.process import ProcessCancelled


class OpenCodeFailureTest(unittest.TestCase):
    def test_process_idle_timeout_resets_on_output(self):
        script = (
            "import json, sys, time\n"
            "for part in ['one', 'two', 'three', 'four']:\n"
            "    print(json.dumps({'type': 'text', 'part': {'text': part}}), flush=True)\n"
            "    time.sleep(0.25)\n"
        )

        stdout, stderr, returncode = _run_process_with_idle_progress(
            [sys.executable, "-c", script],
            "",
            0.6,
            "test progress",
            os.environ.copy(),
        )

        self.assertEqual(returncode, 0)
        self.assertEqual(stderr, [])
        self.assertEqual(len(stdout), 4)

    def test_process_cancellation_stops_active_child(self):
        cancel_event = threading.Event()
        timer = threading.Timer(0.2, cancel_event.set)
        timer.start()
        started_at = time.monotonic()

        with self.assertRaises(ProcessCancelled):
            _run_process_with_idle_progress(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                "",
                20,
                "test cancellation",
                os.environ.copy(),
                cancel_event,
            )

        timer.cancel()
        self.assertLess(time.monotonic() - started_at, 2)

    @patch("core.opencode_client.load_config", return_value={"opencode": {"model": "agnes/agnes-2.0-flash"}})
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
        def execute(prompt, model, idle_timeout_s, task_name, max_attempts=0, cancel_event=None):
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

    @patch("core.opencode_client.run_opencode", return_value="result")
    def test_parallel_collection_accepts_typed_tasks(self, run_single):
        task = Task("typed", "prompt", idle_timeout_s=12, max_attempts=2)

        self.assertEqual(run_parallel([task]), ["result"])
        self.assertEqual(run_single.call_args.args[2:5], (12, "typed", 2))

    @patch("core.opencode_client.run_opencode", return_value="result")
    def test_legacy_timeout_key_is_treated_as_idle_timeout(self, run_single):
        run_parallel([{"name": "legacy", "prompt": "prompt", "timeout_s": 15}])

        self.assertEqual(run_single.call_args.args[2], 15)

    @patch("core.opencode_client.load_config", return_value={"parallel": {"max_workers": 1}})
    @patch("core.opencode_client.run_opencode")
    def test_parallel_collection_does_not_start_queued_work_after_failure(self, run_single, load_config):
        started = []

        def execute(prompt, model, idle_timeout_s, task_name, max_attempts, cancel_event):
            started.append(task_name)
            raise RuntimeError("provider unavailable")

        run_single.side_effect = execute

        with self.assertRaisesRegex(RuntimeError, "first: provider unavailable"):
            run_parallel([
                {"name": "first", "prompt": "one"},
                {"name": "never-started", "prompt": "two"},
            ])

        self.assertEqual(started, ["first"])


if __name__ == "__main__":
    unittest.main()
