import concurrent.futures
import sys
import time


class ProgressTimeoutError(TimeoutError):
    pass


class ProgressBar:
    def __init__(self, label: str, timeout_s: float, width: int = 24, stream=None):
        self.label = label
        self.timeout_s = max(float(timeout_s), 0.1)
        self.width = width
        self.stream = stream or sys.stderr
        self.started_at = time.monotonic()
        self.last_progress_at = self.started_at
        self.last_render_at = 0.0
        self._closed = False

    def mark_progress(self) -> None:
        self.last_progress_at = time.monotonic()
        self.render(force=True)

    def idle_s(self) -> float:
        return time.monotonic() - self.last_progress_at

    def remaining_s(self) -> float:
        return max(0.0, self.timeout_s - self.idle_s())

    def timed_out(self) -> bool:
        return self.idle_s() >= self.timeout_s

    def render(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_render_at < 1:
            return
        self.last_render_at = now
        used = min(self.idle_s() / self.timeout_s, 1.0)
        filled = int(round(self.width * used))
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = now - self.started_at
        message = (
            f"\r[{bar}] {self.label} "
            f"idle={self.idle_s():.0f}s/{self.timeout_s:.0f}s "
            f"elapsed={elapsed:.0f}s"
        )
        print(message, end="", file=self.stream, flush=True)

    def close(self, status: str = "done") -> None:
        if self._closed:
            return
        self._closed = True
        elapsed = time.monotonic() - self.started_at
        print(f"\r[{status}] {self.label} elapsed={elapsed:.1f}s", file=self.stream, flush=True)


def sleep_with_progress(seconds: float, label: str) -> None:
    progress = ProgressBar(label, seconds)
    deadline = time.monotonic() + seconds
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                progress.close("done")
                return
            progress.render()
            time.sleep(min(1.0, remaining))
    except BaseException:
        progress.close("stopped")
        raise


def run_with_progress_timeout(func, timeout_s: float, label: str):
    progress = ProgressBar(label, timeout_s)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func)
    try:
        while True:
            try:
                result = future.result(timeout=1)
            except concurrent.futures.TimeoutError:
                progress.render()
                if progress.timed_out():
                    progress.close("timeout")
                    future.cancel()
                    raise ProgressTimeoutError(f"{label}: no progress for {timeout_s}s")
                continue
            except BaseException:
                progress.close("failed")
                raise
            progress.mark_progress()
            progress.close("done")
            return result
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
