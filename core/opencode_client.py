import subprocess
import json
import os
import shutil
import time
import concurrent.futures
import threading

import shutil

opencode_bin = shutil.which("opencode")
if opencode_bin:
    opencode_bin_dir = os.path.dirname(opencode_bin)
    os.environ.setdefault("PATH", f"{opencode_bin_dir}:" + os.environ.get("PATH", ""))
else:
    opencode_bin_dir = ""


MODEL_FALLBACK = [
    "opencode/mimo-v2.5-free",
    "opencode/deepseek-v4-flash-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/big-pickle",
]


def update_opencode():
    """Run opencode upgrade on startup."""
    try:
        print("[更新] 正在执行 opencode upgrade...")
        env = os.environ.copy()
        if opencode_bin_dir not in env.get("PATH", "").split(":"):
            env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"
        result = subprocess.run(
            [opencode_bin, "upgrade"],
            capture_output=True,
            encoding="utf-8",
            timeout=60,
            env=env,
        )
        if result.returncode == 0:
            print("[upgrade] opencode upgrade done")
            try:
                if result.stdout.strip():
                    print(result.stdout.strip())
            except UnicodeEncodeError:
                pass
        else:
            print(f"[upgrade] opencode upgrade exited with code {result.returncode}")
            try:
                if result.stderr.strip():
                    print(f"[upgrade] stderr: {result.stderr.strip()}")
            except UnicodeEncodeError:
                pass
    except FileNotFoundError:
        print("[upgrade] WARNING: opencode command not found, skipping upgrade")
    except subprocess.TimeoutExpired:
        print("[upgrade] WARNING: opencode upgrade timed out (60s), skipping")
    except Exception as e:
        print(f"[更新] 警告: opencode upgrade 失败: {e}")
def _run_single(prompt: str, model: str, timeout_s: int, label: str) -> tuple[str, bool]:
    """Run opencode with a single model. Returns (result_text, success)."""
    env = os.environ.copy()
    from core.config import load_config
    permissions = load_config().get("opencode", {}).get("permissions", {})
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": permissions})
    if opencode_bin_dir not in env.get("PATH", "").split(":"):
        env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"
    cmd = ["opencode", "run", prompt, "--format", "json", "-m", model]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        encoding="utf-8",
    )

    timed_out = threading.Event()
    def _kill_on_timeout():
        timed_out.set()
        print(f"  [timeout] {label} ({model}) exceeded {timeout_s}s, killing...", flush=True)
        try:
            proc.kill()
        except OSError:
            pass
    timer = threading.Timer(timeout_s, _kill_on_timeout)
    timer.start()
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except OSError:
        pass
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s + 5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    timer.cancel()

    text_parts = []
    for line in (stdout or "").splitlines():
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
    was_killed = timed_out.is_set() or proc.returncode == -9
    success = bool(result.strip()) and not was_killed
    return result, success


def run_opencode(prompt: str, model: str = "", timeout_s: int = 0, task_name: str = "") -> str:
    from core.config import load_config
    cfg = load_config().get("opencode", {})
    timeout_s = timeout_s or cfg.get("timeout_s", 300)
    label = task_name or "task"

    if model:
        models_to_try = [model]
    else:
        models_to_try = list(MODEL_FALLBACK)

    result = ""
    for m in models_to_try:
        print(f"  [start] {label} ({m})", flush=True)
        t_start = time.time()
        result, success = _run_single(prompt, m, timeout_s, label)
        elapsed = time.time() - t_start
        result_len = len(result)

        if success:
            print(f"  [done] {label} ({m}) ({elapsed:.1f}s, {result_len} chars)", flush=True)
            return result

        print(f"  [fail] {label} ({m}) ({elapsed:.1f}s, {result_len}c) -> trying next model", flush=True)

    print(f"  [all failed] {label} all models failed, returning last result", flush=True)
    return result


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
            )
            future_map[f] = task.get("name", "")
        results = []
        for f in concurrent.futures.as_completed(future_map):
            name = future_map[f]
            try:
                result = f.result()
                results.append((name, result))
            except Exception as e:
                results.append((name, f"[{name}] Error: {e}"))
    task_names = [t["name"] for t in tasks]
    results.sort(key=lambda x: task_names.index(x[0]))
    return [r[1] for r in results]
