#!/bin/bash
# Mac Mini wrapper for the PO Agent (docs/macmini-setup.md section 8).
#
#   scripts/macmini-run.sh <run|spike|decide-only>
#
# 1. git pull --ff-only, uv sync --locked, uv run playwright install chromium.
#    If any fails, the agent doesn't run (stale code would ignore
#    enabled = false on main): a fixed line to runs.log, an alert issue, exit 2.
# 2. Runs the agent on the test site (never --detailed-log) with a hard time
#    limit, in its own process group, and kills the whole group plus this
#    user's Playwright browsers when it ends or hits the limit, so nothing
#    overlaps the next run.
# 3. Appends a timestamp line and the agent's stdout to runs.log; its stderr
#    goes to /dev/null (a crash's text could quote page content).
# 4. On any ALERT line or a non-zero exit, opens a GitHub issue labelled
#    po-agent-alert whose body is only the ALERT lines and the exit code.
#
# Written for macOS's /bin/bash 3.2: no GNU timeout, no setsid.

set -u

# launchd starts jobs with a minimal environment. MACMINI_RUN_PATH_PREFIX
# goes first so the tests' stub commands win.
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
if [ -n "${MACMINI_RUN_PATH_PREFIX:-}" ]; then
  PATH="$MACMINI_RUN_PATH_PREFIX:$PATH"
fi
export PATH

LIMIT_S="${MACMINI_RUN_LIMIT_S:-1200}" # 20 minutes; the tests shorten it
GRACE_S=10                              # SIGTERM, then SIGKILL after this
LOG_DIR="$HOME/Library/Logs/po-agent"
RUNS_LOG="$LOG_DIR/runs.log"

usage() {
  echo "usage: macmini-run.sh <run|spike|decide-only>" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
case "$1" in
  run) AGENT_ARGS="run --site test" ;;
  spike) AGENT_ARGS="spike --site test" ;;
  decide-only) AGENT_ARGS="run --decide-only --site test" ;;
  *) usage ;;
esac
MODE="$1"

cd "$(dirname "$0")/.." || exit 2
mkdir -p "$LOG_DIR" || exit 2
OUT="$(mktemp "${TMPDIR:-/tmp}/po-agent-run.XXXXXX")" || exit 2
AGENT_PID=""

log() {
  echo "$1" >> "$RUNS_LOG"
}

# $1 = run_id or "no run_id", $2 = exit code, $3 = an optional fixed wrapper
# line. The body is the ALERT lines from $OUT, that line and the exit code.
open_issue() {
  local body
  body="$(grep '^ALERT ' "$OUT")"
  if [ -n "${3:-}" ]; then
    body="${body:+$body
}$3"
  fi
  body="${body:+$body
}exit code: $2"
  if ! gh issue create --label po-agent-alert --title "po-agent alert $1" \
    --body "$body" > /dev/null 2>&1; then
    log "wrapper: alert issue not opened"
  fi
}

# Stops the agent's process group: SIGTERM, then SIGKILL after GRACE_S.
# Playwright starts Chromium detached (its own process group), so the group
# kill can't reach it: then every Playwright browser of this user is killed.
# Only one agent runs on the Mac Mini at a time (docs/macmini-setup.md).
stop_group() {
  local waited=0
  [ -n "$AGENT_PID" ] || return 0
  if kill -TERM -- "-$AGENT_PID" 2> /dev/null; then
    while kill -0 -- "-$AGENT_PID" 2> /dev/null && [ "$waited" -lt "$GRACE_S" ]; do
      sleep 1
      waited=$((waited + 1))
    done
    kill -KILL -- "-$AGENT_PID" 2> /dev/null
  fi
  if pkill -KILL -u "$(id -u)" -f 'ms-playwright/' 2> /dev/null; then
    log "wrapper: leftover Playwright browser killed"
  fi
  return 0
}

cleanup() {
  stop_group
  rm -f "$OUT"
}
trap cleanup EXIT
trap 'exit 1' INT TERM HUP

log "=== $(date '+%Y-%m-%dT%H:%M:%S%z') macmini-run.sh $MODE ==="

setup_failed() { # $1 = the step that failed
  local line="wrapper: setup failed ($1), agent not run"
  log "$line"
  open_issue "no run_id" 2 "$line"
  exit 2
}
# Their own output goes to launchd.log (the plist's StandardOutPath).
git pull --ff-only || setup_failed "git pull"
uv sync --locked || setup_failed "uv sync"
uv run playwright install chromium || setup_failed "playwright install"

# Job control puts the background agent in its own process group (pgid = its
# pid), so one kill reaches uv, Python and Playwright's driver.
set -m
# shellcheck disable=SC2086  # AGENT_ARGS is a fixed word list from above
uv run po-agent $AGENT_ARGS > "$OUT" 2> /dev/null < /dev/null &
AGENT_PID=$!
set +m

started=$SECONDS # wall-clock seconds, not loop passes
timed_out=0
while kill -0 "$AGENT_PID" 2> /dev/null; do
  if [ $((SECONDS - started)) -ge "$LIMIT_S" ]; then
    timed_out=1
    break
  fi
  sleep 1
done

if [ "$timed_out" -eq 1 ]; then
  stop_group
  wait "$AGENT_PID" 2> /dev/null
  code=1
else
  wait "$AGENT_PID"
  code=$?
  stop_group # anything the agent left behind, browsers included
fi
AGENT_PID=""

cat "$OUT" >> "$RUNS_LOG"
note=""
if [ "$timed_out" -eq 1 ]; then
  note="wrapper: agent killed at the ${LIMIT_S}s limit"
  log "$note"
fi

if [ "$code" -ne 0 ] || grep -q '^ALERT ' "$OUT"; then
  run_id="$(sed -n 's/^RUN_SUMMARY {"run_id": "\([0-9]\{8\}T[0-9]\{6\}Z-[0-9a-f]\{4\}\)".*/\1/p' "$OUT" | tail -n 1)"
  open_issue "${run_id:-no run_id}" "$code" "$note"
fi
exit "$code"
