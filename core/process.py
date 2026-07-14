import queue
import subprocess
import threading

from core.progress import ProgressBar


class ProcessCancelled(RuntimeError):
    pass


def run_process_with_idle_progress(
    command: list[str],
    input_text: str,
    idle_timeout_s: float,
    label: str,
    env: dict,
    cancel_event: threading.Event | None = None,
) -> tuple[list[str], list[str], int]:
    """Capture a process, resetting its idle timer whenever either stream emits a line."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        encoding="utf-8",
    )
    if process.stdin:
        process.stdin.write(input_text)
        process.stdin.close()

    output = queue.Queue()
    threads = [
        threading.Thread(
            target=_read_stream,
            args=(process.stdout, "stdout", output),
            daemon=True,
        ),
        threading.Thread(
            target=_read_stream,
            args=(process.stderr, "stderr", output),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    streams = {"stdout": [], "stderr": []}
    progress = ProgressBar(label, idle_timeout_s)
    try:
        while True:
            if cancel_event and cancel_event.is_set():
                process.kill()
                process.wait()
                progress.close("cancelled")
                raise ProcessCancelled(f"{label} cancelled")
            try:
                stream_name, line = output.get(timeout=0.25)
            except queue.Empty:
                progress.render()
                if process.poll() is not None:
                    break
                if progress.timed_out():
                    process.kill()
                    process.wait()
                    progress.close("timeout")
                    raise subprocess.TimeoutExpired(command, idle_timeout_s)
                continue

            streams[stream_name].append(line)
            progress.mark_progress()
            if process.poll() is not None and output.empty():
                break
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        progress.close("stopped")
        raise
    finally:
        for thread in threads:
            thread.join(timeout=1)
        _drain_output(output, streams)

    returncode = process.wait()
    progress.close("done" if returncode == 0 else f"exit {returncode}")
    return streams["stdout"], streams["stderr"], returncode


def _read_stream(pipe, stream_name: str, output: queue.Queue) -> None:
    try:
        for line in iter(pipe.readline, ""):
            output.put((stream_name, line))
    finally:
        pipe.close()


def _drain_output(output: queue.Queue, streams: dict[str, list[str]]) -> None:
    while True:
        try:
            stream_name, line = output.get_nowait()
        except queue.Empty:
            return
        streams[stream_name].append(line)
