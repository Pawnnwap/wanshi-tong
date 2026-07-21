"""Tiny wall-clock timeout helper using a daemon thread.

`concurrent.futures.ThreadPoolExecutor`'s `with` block calls
`shutdown(wait=True)` on exit, which blocks forever if the worker thread is
hung on a network call -- even after `future.result(timeout=...)` has already
raised `TimeoutError`. The hung non-daemon worker also keeps the interpreter
alive at process exit. This helper sidesteps both issues: the runner thread is
a daemon (won't block interpreter exit) and we never call `shutdown(wait=True)`.
"""

from __future__ import annotations

import queue
import threading


def run_with_timeout(fn, timeout_s: float, label: str = "task"):
    """Run ``fn()`` in a daemon thread, waiting at most ``timeout_s`` seconds.

    Returns ``fn``'s return value on success. Raises ``TimeoutError`` if the
    wall-clock budget expires (the daemon thread is left running and dies when
    the process exits). Any exception raised by ``fn`` is re-raised here.
    """
    result_q: "queue.Queue[tuple]" = queue.Queue()

    def runner():
        try:
            result_q.put(("ok", fn()))
        except BaseException as exc:  # noqa: BLE001 -- forward to caller verbatim
            result_q.put(("error", exc))

    t = threading.Thread(target=runner, name=f"timeout-{label}", daemon=True)
    t.start()
    try:
        status, value = result_q.get(timeout=timeout_s)
    except queue.Empty:
        raise TimeoutError(f"{label} timed out after {timeout_s}s")
    if status == "error":
        raise value
    return value