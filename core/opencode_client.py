import subprocess
import json
import os
import queue
import shutil
import threading
import time
import concurrent.futures

from core.progress import ProgressBar, sleep_with_progress


opencode_bin = shutil.which("opencode")
if opencode_bin:
    opencode_bin_dir = os.path.dirname(opencode_bin)
    os.environ.setdefault("PATH", f"{opencode_bin_dir}:" + os.environ.get("PATH", ""))
else:
    opencode_bin_dir = ""


MODEL_FALLBACK = [
    "agnes/agnes-2.0-flash",
    "opencode/deepseek-v4-flash-free",
    "opencode/mimo-v2.5-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/big-pickle",
]


def _reader_thread(pipe, stream_name: str, output: queue.Queue) -> None:
    try:
        for line in iter(pipe.readline, ""):
            output.put((stream_name, line))
    finally:
        pipe.close()


def _run_process_with_idle_progress(
    cmd: list[str],
    input_text: str,
    timeout_s: int,
    label: str,
    env: dict,
) -> tuple[list[str], list[str], int]:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        encoding="utf-8",
    )
    if proc.stdin:
        proc.stdin.write(input_text)
        proc.stdin.close()

    output = queue.Queue()
    threads = [
        threading.Thread(target=_reader_thread, args=(proc.stdout, "stdout", output), daemon=True),
        threading.Thread(target=_reader_thread, args=(proc.stderr, "stderr", output), daemon=True),
    ]
    for thread in threads:
        thread.start()

    stdout_lines = []
    stderr_lines = []
    progress = ProgressBar(label, timeout_s)
    try:
        while True:
            try:
                stream_name, line = output.get(timeout=0.25)
            except queue.Empty:
                progress.render()
                if proc.poll() is not None:
                    break
                if progress.timed_out():
                    proc.kill()
                    proc.wait()
                    progress.close("timeout")
                    raise subprocess.TimeoutExpired(cmd, timeout_s)
                continue

            progress.mark_progress()
            if stream_name == "stdout":
                stdout_lines.append(line)
            else:
                stderr_lines.append(line)

            if proc.poll() is not None and output.empty():
                break
    finally:
        for thread in threads:
            thread.join(timeout=1)
        while True:
            try:
                stream_name, line = output.get_nowait()
            except queue.Empty:
                break
            if stream_name == "stdout":
                stdout_lines.append(line)
            else:
                stderr_lines.append(line)

    returncode = proc.wait()
    progress.close("done" if returncode == 0 else f"exit {returncode}")
    return stdout_lines, stderr_lines, returncode


def update_opencode():
    """Run opencode upgrade on startup."""
    try:
        print("[更新] 正在执行 opencode upgrade...")
        env = os.environ.copy()
        if opencode_bin_dir not in env.get("PATH", "").split(":"):
            env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"
        stdout_lines, stderr_lines, returncode = _run_process_with_idle_progress(
            [opencode_bin, "upgrade"],
            "",
            60,
            "opencode upgrade",
            env,
        )
        if returncode == 0:
            print("[upgrade] opencode upgrade done")
            try:
                stdout = "".join(stdout_lines).strip()
                if stdout:
                    print(stdout)
            except UnicodeEncodeError:
                pass
        else:
            print(f"[upgrade] opencode upgrade exited with code {returncode}")
            try:
                stderr = "".join(stderr_lines).strip()
                if stderr:
                    print(f"[upgrade] stderr: {stderr}")
            except UnicodeEncodeError:
                pass
    except FileNotFoundError:
        print("[upgrade] WARNING: opencode command not found, skipping upgrade")
    except subprocess.TimeoutExpired:
        print("[upgrade] WARNING: opencode upgrade timed out (60s), skipping")
    except Exception as e:
        print(f"[更新] 警告: opencode upgrade 失败: {e}")
def _run_single(prompt: str, model: str, timeout_s: int, label: str, max_attempts: int = 0) -> tuple[str, bool]:
    """Run opencode with a single model. Returns (result_text, success)."""
    env = os.environ.copy()
    from core.config import load_config
    permissions = load_config().get("opencode", {}).get("permissions", {})
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": permissions})
    if opencode_bin_dir not in env.get("PATH", "").split(":"):
        env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"
    cmd = ["opencode", "run", prompt, "--format", "json", "-m", model]
    max_attempts = max_attempts or (3 if model.startswith("agnes/") else 1)
    stdout_lines = []
    stderr_lines = []
    returncode = -9

    for attempt in range(1, max_attempts + 1):
        try:
            stdout_lines, stderr_lines, returncode = _run_process_with_idle_progress(
                cmd,
                prompt,
                timeout_s,
                f"{label} ({model}) attempt {attempt}/{max_attempts}",
                env,
            )
        except subprocess.TimeoutExpired:
            stdout_lines = []
            stderr_lines = []
            returncode = -9

        if returncode == 0:
            break

        stderr = "".join(stderr_lines).strip()
        if stderr:
            print(f"  [stderr] {label} ({model}): {stderr[:1000]}", flush=True)
        if attempt < max_attempts:
            sleep_with_progress(10 * attempt, f"retry {label} ({model})")

    text_parts = []
    for line in stdout_lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            t = event.get("part", {}).get("text", "")
            if t:
                text_parts.append(t)

    result = "".join(text_parts)
    was_killed = returncode == -9
    success = returncode == 0 and bool(result.strip()) and not was_killed
    return result, success


def run_opencode(
    prompt: str,
    model: str = "",
    timeout_s: int = 0,
    task_name: str = "",
    max_attempts: int = 0,
) -> str:
    from core.config import load_config
    cfg = load_config().get("opencode", {})
    timeout_s = timeout_s or cfg.get("timeout_s", 600)
    label = task_name or "task"

    if model:
        models_to_try = [model]
    else:
        configured_model = cfg.get("model", "")
        models_to_try = []
        if configured_model:
            models_to_try.append(configured_model)
        if not configured_model.startswith("agnes/"):
            models_to_try.extend(m for m in MODEL_FALLBACK if m not in models_to_try)

    result = ""
    for m in models_to_try:
        print(f"  [start] {label} ({m})", flush=True)
        t_start = time.time()
        result, success = _run_single(prompt, m, timeout_s, label, max_attempts=max_attempts)
        elapsed = time.time() - t_start
        result_len = len(result)

        if success:
            print(f"  [done] {label} ({m}) ({elapsed:.1f}s, {result_len} chars)", flush=True)
            return result

        print(f"  [fail] {label} ({m}) ({elapsed:.1f}s, {result_len}c) -> trying next model", flush=True)

    raise RuntimeError(f"{label}: all configured models failed")


def run_parallel(tasks: list[dict]) -> list[str]:
    from core.config import load_config
    cfg = load_config().get("parallel", {})
    max_workers = cfg.get("max_workers", 5)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {}
        for task in tasks:
            f = pool.submit(
                run_opencode,
                task["prompt"],
                task.get("model", ""),
                task.get("timeout_s", 0),
                task.get("name", ""),
                task.get("max_attempts", 0),
            )
            future_map[f] = task.get("name", "")
        results = []
        errors = []
        for f in concurrent.futures.as_completed(future_map):
            name = future_map[f]
            try:
                result = f.result()
                results.append((name, result))
            except Exception as e:
                errors.append(f"{name}: {e}")
    if errors:
        raise RuntimeError("parallel collection failed: " + "; ".join(errors))
    task_names = [t["name"] for t in tasks]
    results.sort(key=lambda x: task_names.index(x[0]))
    return [r[1] for r in results]
