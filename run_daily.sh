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

render_progress_bar() {
    local label="$1"
    local idle="$2"
    local timeout="$3"
    local elapsed="$4"
    local width=24
    if (( timeout < 1 )); then
        timeout=1
    fi
    local filled=$(( idle * width / timeout ))
    if (( filled > width )); then
        filled=$width
    fi
    local empty=$(( width - filled ))
    printf '\r['
    printf '%*s' "$filled" '' | tr ' ' '#'
    printf '%*s' "$empty" '' | tr ' ' '-'
    printf '] %s idle=%ss/%ss elapsed=%ss' "$label" "$idle" "$timeout" "$elapsed"
}

run_attempt_with_progress() {
    local attempt="$1"
    local attempt_log="$LOG_DIR/attempt_${$}_${attempt}.log"
    local start_ts last_progress_ts now idle elapsed size last_size exit_code proc_state
    : >"$attempt_log"

    "$PYTHON_BIN" "$MAIN_SCRIPT" >"$attempt_log" 2>&1 &
    local child_pid=$!
    start_ts=$(date +%s)
    last_progress_ts=$start_ts
    last_size=0

    while kill -0 "$child_pid" 2>/dev/null; do
        proc_state=$(ps -p "$child_pid" -o stat= 2>/dev/null || true)
        if [[ "$proc_state" == Z* ]]; then
            break
        fi
        now=$(date +%s)
        size=$(stat -c '%s' "$attempt_log" 2>/dev/null || printf '0')
        if (( size > last_size )); then
            tail -c +"$((last_size + 1))" "$attempt_log"
            last_size=$size
            last_progress_ts=$now
        fi

        idle=$((now - last_progress_ts))
        elapsed=$((now - start_ts))
        render_progress_bar "attempt $attempt/$MAX_ATTEMPTS" "$idle" "$ATTEMPT_TIMEOUT_SECONDS" "$elapsed"
        if (( idle >= ATTEMPT_TIMEOUT_SECONDS )); then
            printf '\n'
            log "Attempt $attempt made no output progress for ${ATTEMPT_TIMEOUT_SECONDS}s; terminating."
            kill -TERM "$child_pid" 2>/dev/null || true
            sleep 60 &
            local grace_pid=$!
            while kill -0 "$child_pid" 2>/dev/null && kill -0 "$grace_pid" 2>/dev/null; do
                proc_state=$(ps -p "$child_pid" -o stat= 2>/dev/null || true)
                if [[ "$proc_state" == Z* ]]; then
                    break
                fi
                sleep 1
            done
            kill "$grace_pid" 2>/dev/null || true
            if kill -0 "$child_pid" 2>/dev/null; then
                kill -KILL "$child_pid" 2>/dev/null || true
            fi
            wait "$child_pid" 2>/dev/null || true
            rm -f "$attempt_log"
            return 124
        fi
        sleep 1
    done

    wait "$child_pid"
    exit_code=$?
    size=$(stat -c '%s' "$attempt_log" 2>/dev/null || printf '0')
    if (( size > last_size )); then
        tail -c +"$((last_size + 1))" "$attempt_log"
    fi
    printf '\n'
    rm -f "$attempt_log"
    return "$exit_code"
}

sleep_with_progress() {
    local seconds="$1"
    local label="$2"
    local start_ts now elapsed remaining
    start_ts=$(date +%s)
    while true; do
        now=$(date +%s)
        elapsed=$((now - start_ts))
        if (( elapsed >= seconds )); then
            printf '\r[done] %s elapsed=%ss\n' "$label" "$elapsed"
            return 0
        fi
        remaining=$((seconds - elapsed))
        render_progress_bar "$label" "$elapsed" "$seconds" "$elapsed"
        sleep 1
    done
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
    run_attempt_with_progress "$attempt"
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
        sleep_with_progress "$RETRY_DELAY_SECONDS" "retry delay"
    fi
done

log "Daily run failed after $MAX_ATTEMPTS attempts."
cleanup_logs
exit "$exit_code"
