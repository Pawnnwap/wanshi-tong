import concurrent.futures
import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence

from core.base import Task
from core.config import load_config
from core.process import ProcessCancelled
from core.process import run_process_with_idle_progress as _run_process_with_idle_progress
from core.progress import sleep_with_progress


OPENCODE_BIN = shutil.which("opencode")
MODEL_FALLBACK = (
    "agnes/agnes-2.0-flash",
    "opencode/deepseek-v4-flash-free",
    "opencode/mimo-v2.5-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/big-pickle",
)


def _opencode_env(include_permissions: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    if OPENCODE_BIN:
        binary_dir = os.path.dirname(OPENCODE_BIN)
        path_parts = env.get("PATH", "").split(os.pathsep)
        if binary_dir not in path_parts:
            env["PATH"] = os.pathsep.join([binary_dir, *path_parts])
    if include_permissions:
        permissions = load_config().get("opencode", {}).get("permissions", {})
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": permissions})
    return env


def _executable() -> str:
    if not OPENCODE_BIN:
        raise FileNotFoundError("opencode command not found")
    return OPENCODE_BIN


def update_opencode() -> None:
    """Upgrade OpenCode without making startup depend on upgrade availability."""
    try:
        print("[update] running opencode upgrade...")
        stdout, stderr, returncode = _run_process_with_idle_progress(
            [_executable(), "upgrade"],
            "",
            60,
            "opencode upgrade",
            _opencode_env(),
        )
        if returncode == 0:
            print("[upgrade] opencode upgrade done")
            if output := "".join(stdout).strip():
                print(output)
        else:
            print(f"[upgrade] opencode upgrade exited with code {returncode}")
            if output := "".join(stderr).strip():
                print(f"[upgrade] stderr: {output}")
    except FileNotFoundError:
        print("[upgrade] WARNING: opencode command not found, skipping upgrade")
    except subprocess.TimeoutExpired:
        print("[upgrade] WARNING: opencode upgrade had no output for 60s, skipping")
    except Exception as exc:
        print(f"[upgrade] WARNING: opencode upgrade failed: {exc}")


def _run_single(
    prompt: str,
    model: str,
    idle_timeout_s: float,
    label: str,
    max_attempts: int = 0,
    cancel_event: threading.Event | None = None,
) -> tuple[str, bool]:
    """Run one model, retrying provider failures while output remains idle-aware."""
    attempts = max_attempts or (3 if model.startswith("agnes/") else 1)
    command = [_executable(), "run", prompt, "--format", "json", "-m", model]
    stdout: list[str] = []
    stderr: list[str] = []
    returncode = -9

    for attempt in range(1, attempts + 1):
        if cancel_event and cancel_event.is_set():
            raise ProcessCancelled(f"{label} cancelled")
        try:
            stdout, stderr, returncode = _run_process_with_idle_progress(
                command,
                prompt,
                idle_timeout_s,
                f"{label} ({model}) attempt {attempt}/{attempts}",
                _opencode_env(include_permissions=True),
                cancel_event,
            )
        except subprocess.TimeoutExpired:
            stdout, stderr, returncode = [], [], -9

        if returncode == 0:
            break
        if error_output := "".join(stderr).strip():
            print(f"  [stderr] {label} ({model}): {error_output[:1000]}", flush=True)
        if attempt < attempts:
            if not sleep_with_progress(
                10 * attempt,
                f"retry {label} ({model})",
                cancel_event,
            ):
                raise ProcessCancelled(f"{label} cancelled")

    result = _parse_text_events(stdout)
    return result, returncode == 0 and bool(result.strip())


def _parse_text_events(lines: Sequence[str]) -> str:
    text_parts = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text" and (text := event.get("part", {}).get("text", "")):
            text_parts.append(text)
    return "".join(text_parts)


def run_opencode(
    prompt: str,
    model: str = "",
    idle_timeout_s: float = 0,
    task_name: str = "",
    max_attempts: int = 0,
    cancel_event: threading.Event | None = None,
    **legacy_options,
) -> str:
    if "timeout_s" in legacy_options:
        idle_timeout_s = idle_timeout_s or legacy_options.pop("timeout_s")
    if legacy_options:
        names = ", ".join(sorted(legacy_options))
        raise TypeError(f"unexpected options: {names}")

    config = load_config().get("opencode", {})
    idle_timeout_s = idle_timeout_s or config.get("idle_timeout_s", config.get("timeout_s", 600))
    label = task_name or "task"

    for candidate in _models_to_try(model, config.get("model", "")):
        print(f"  [start] {label} ({candidate})", flush=True)
        started_at = time.monotonic()
        result, success = _run_single(
            prompt,
            candidate,
            idle_timeout_s,
            label,
            max_attempts=max_attempts,
            cancel_event=cancel_event,
        )
        elapsed = time.monotonic() - started_at
        if success:
            print(f"  [done] {label} ({candidate}) ({elapsed:.1f}s, {len(result)} chars)", flush=True)
            return result
        print(
            f"  [fail] {label} ({candidate}) ({elapsed:.1f}s, {len(result)}c) -> trying next model",
            flush=True,
        )
    raise RuntimeError(f"{label}: all configured models failed")


def _models_to_try(requested: str, configured: str) -> list[str]:
    if requested:
        return [requested]
    models = [configured] if configured else []
    if not configured.startswith("agnes/"):
        models.extend(model for model in MODEL_FALLBACK if model not in models)
    return models


def run_parallel(tasks: Sequence[Task | Mapping]) -> list[str]:
    normalized = [Task.from_value(task) for task in tasks]
    max_workers = load_config().get("parallel", {}).get("max_workers", 5)
    results = [""] * len(normalized)
    errors = []
    cancel_event = threading.Event()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    future_map = {}
    task_iterator = iter(enumerate(normalized))

    def submit_next() -> bool:
        try:
            index, task = next(task_iterator)
        except StopIteration:
            return False
        future = pool.submit(
            run_opencode,
            task.prompt,
            task.model,
            task.idle_timeout_s,
            task.name,
            task.max_attempts,
            cancel_event,
        )
        future_map[future] = (index, task.name)
        return True

    try:
        for _ in range(min(max_workers, len(normalized))):
            submit_next()

        while future_map:
            future = next(concurrent.futures.as_completed(tuple(future_map)))
            index, name = future_map[future]
            del future_map[future]
            try:
                results[index] = future.result()
            except (concurrent.futures.CancelledError, ProcessCancelled):
                if not cancel_event.is_set():
                    raise
            except Exception as exc:
                if not errors:
                    errors.append((index, f"{name}: {exc}"))
                    cancel_event.set()
                    for pending in future_map:
                        pending.cancel()
            if errors:
                break
            submit_next()
    except BaseException:
        cancel_event.set()
        for future in future_map:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    if errors:
        errors.sort()
        raise RuntimeError("parallel collection failed: " + "; ".join(message for _, message in errors))
    return results
