#!/usr/bin/env bash
set -uo pipefail

PROJECT_DIR="/home/aaa/pyprojects/wanshi-tong"
LOG_DIR="$PROJECT_DIR/logs"
STATE_DIR="$LOG_DIR/state"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/wanshi-tong-${UID}.lock"
PYTHON_BIN="${WANSHI_TONG_PYTHON_BIN:-/usr/bin/python3}"
MAIN_SCRIPT="${WANSHI_TONG_MAIN_SCRIPT:-$PROJECT_DIR/main.py}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-600}"
ATTEMPT_TIMEOUT_SECONDS="${ATTEMPT_TIMEOUT_SECONDS:-7200}"

export HOME="/home/aaa"
export PATH="/home/aaa/.opencode/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p "$LOG_DIR" "$STATE_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S)_${$}.log"
exec >>"$LOG_FILE" 2>&1

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"
}

cleanup_logs() {
    find "$LOG_DIR" -maxdepth 1 -type f -name 'run_*.log' -printf '%T@ %p\n' \
        | sort -nr \
        | awk 'NR > 30 {sub(/^[^ ]+ /, ""); print}' \
        | while IFS= read -r old_log; do
            rm -f -- "$old_log"
        done
    find "$STATE_DIR" -type f -name 'success_*' -mtime +14 -delete
}

exec 9>"$LOCK_FILE"
if ! /usr/bin/flock -n 9; then
    log "Another daily run is active; skipping this invocation."
    exit 0
fi

SUCCESS_MARKER="$STATE_DIR/success_$(date +%Y%m%d)"
if [[ "${1:-}" == "--if-missed" ]]; then
    current_minutes=$((10#$(date +%H) * 60 + 10#$(date +%M)))
    if (( current_minutes < 600 )); then
        log "Reboot catch-up skipped before the 10:00 schedule."
        exit 0
    fi
    if [[ -f "$SUCCESS_MARKER" ]]; then
        log "Today's run already succeeded; reboot catch-up skipped."
        exit 0
    fi
elif [[ $# -gt 0 ]]; then
    log "Unknown argument: $1"
    exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    log "Python executable not found: $PYTHON_BIN"
    exit 1
fi
if [[ ! -x "/home/aaa/.opencode/bin/opencode" ]]; then
    log "OpenCode executable not found: /home/aaa/.opencode/bin/opencode"
    exit 1
fi
for required_file in "$MAIN_SCRIPT" "$PROJECT_DIR/config.json" "$PROJECT_DIR/credentials.json"; do
    if [[ ! -r "$required_file" ]]; then
        log "Required file is not readable: $required_file"
        exit 1
    fi
done

cd "$PROJECT_DIR" || {
    log "Cannot enter project directory: $PROJECT_DIR"
    exit 1
}

exit_code=1
for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    log "Starting attempt $attempt/$MAX_ATTEMPTS."
    /usr/bin/timeout \
        --signal=TERM \
        --kill-after=60s \
        "${ATTEMPT_TIMEOUT_SECONDS}s" \
        "$PYTHON_BIN" "$MAIN_SCRIPT"
    exit_code=$?

    if (( exit_code == 0 )); then
        touch "$SUCCESS_MARKER"
        log "Daily run succeeded on attempt $attempt."
        cleanup_logs
        exit 0
    fi

    if (( exit_code == 124 )); then
        log "Attempt $attempt exceeded ${ATTEMPT_TIMEOUT_SECONDS}s."
    else
        log "Attempt $attempt failed with exit code $exit_code."
    fi

    if (( attempt < MAX_ATTEMPTS )); then
        log "Retrying in ${RETRY_DELAY_SECONDS}s."
        /usr/bin/sleep "$RETRY_DELAY_SECONDS"
    fi
done

log "Daily run failed after $MAX_ATTEMPTS attempts."
cleanup_logs
exit "$exit_code"
