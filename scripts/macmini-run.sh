#!/bin/bash
# Mac Mini wrapper for the PO Agent (docs/macmini-setup.md section 8).
#
#   scripts/macmini-run.sh <run|spike|decide-only> <test|live>
#
# The site is required, with no default (decisions, 10 Nov 2026, live
# profile): after go-live launchd runs `run live`. Only launchd or Joey runs
# it on live; Claude never does (CLAUDE.md Must never #3).
#
# 1. Release pinning (plan task 7.4): fetches origin (moved and deleted tags
#    too), reads enabled from config/<site>.toml on origin/main (false: a
#    fixed line to runs.log, exit 0, nothing else run), then checks out the
#    production tag's commit, detached. Only Joey moves that tag, by hand;
#    this script never creates, moves or pushes it. Then uv sync --locked and
#    uv run playwright install chromium. If any step fails, or enabled on main
#    isn't exactly one "enabled = true|false" line, the agent doesn't run:
#    a fixed line to runs.log, an alert issue, exit 2.
# 2. Runs the agent on that site (never --detailed-log) with a hard time
#    limit, in its own process group, and kills the whole group plus this
#    user's Playwright browsers when it ends or hits the limit, so nothing
#    overlaps the next run.
# 3. Appends a timestamp line and the agent's stdout to runs.log; its stderr
#    goes to /dev/null (a crash's text could quote page content).
# 4. On any ALERT line or a non-zero exit, opens a GitHub issue labelled
#    po-agent-alert whose body is only the ALERT lines, without any Note ID
#    (the repo is public; audit N4), and the exit code. runs.log keeps the
#    ALERT lines whole.
# 5. At the end of every run, whatever the exit code (a failed setup and a
#    killed agent too), pings: the body of the one open issue labelled
#    po-agent-heartbeat becomes the time, the exit code and the run_id. The
#    heartbeat workflow (.github/workflows/heartbeat.yml) opens an alert when
#    no ping arrives for 2 hours inside the schedule. A failed ping only logs
#    a fixed line; it never changes the exit code.
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
GH_LIMIT_S="${MACMINI_RUN_GH_LIMIT_S:-60}" # per gh call; the tests shorten it
LOG_DIR="$HOME/Library/Logs/po-agent"
RUNS_LOG="$LOG_DIR/runs.log"

usage() {
  echo "usage: macmini-run.sh <run|spike|decide-only> <test|live>" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
case "$2" in
  test | live) SITE="$2" ;;
  *) usage ;;
esac
case "$1" in
  run) AGENT_ARGS="run --site $SITE" ;;
  spike) AGENT_ARGS="spike --site $SITE" ;;
  decide-only) AGENT_ARGS="run --decide-only --site $SITE" ;;
  *) usage ;;
esac
MODE="$1"
OUT=""
AGENT_PID=""
run_id="" # from the agent's RUN_SUMMARY line, if it printed one

cd "$(dirname "$0")/.." || exit 2

log() {
  echo "$1" >> "$RUNS_LOG"
}

# gh with a GH_LIMIT_S time limit (no GNU timeout on macOS): a hung gh would
# keep this wrapper running, and launchd skips every later run while it does.
# Returns gh's exit code, or 1 if it was killed at the limit.
gh_limited() {
  local pid waited=0
  gh "$@" &
  pid=$!
  while kill -0 "$pid" 2> /dev/null; do
    if [ "$waited" -ge "$GH_LIMIT_S" ]; then
      kill -KILL "$pid" 2> /dev/null
      wait "$pid" 2> /dev/null
      return 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
}

# The ALERT lines from $OUT without any Note ID (audit N4): the JSON key and
# the detail's "note_id=<id>" (core/errors.py) are cut; a line that still
# names one, in any case, keeps only "ALERT <KIND>".
public_alerts() {
  grep '^ALERT ' "$OUT" | sed -E \
    -e 's/"note_id": *("[^"]*"|null), *//g' \
    -e 's/, *"note_id": *("[^"]*"|null)//g' \
    -e 's/ \(note_id=[^,)]*\)//g' \
    -e 's/\(note_id=[^,)]*, */(/g' \
    -e 's/, *note_id=[^,)]*//g' |
    while IFS= read -r line; do
      if printf '%s\n' "$line" | grep -qi 'note_id'; then
        printf '%s\n' "$line" | cut -d ' ' -f 1-2
      else
        printf '%s\n' "$line"
      fi
    done
}

# $1 = run_id or "no run_id", $2 = exit code, $3 = an optional fixed wrapper
# line. The body is the public ALERT lines, that line and the exit code.
open_issue() {
  local body
  body="$(public_alerts)"
  if [ -n "${3:-}" ]; then
    body="${body:+$body
}$3"
  fi
  body="${body:+$body
}exit code: $2"
  if ! gh_limited issue create --label po-agent-alert --title "po-agent alert $1" \
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

# The ping (step 5). gh finds the repo from this checkout's remote, as for
# the alert issue. No PO data: only the time, $1 (the exit code) and run_id.
heartbeat() {
  local issue
  issue="$(gh_limited issue list --label po-agent-heartbeat --state open --limit 1 \
    --json number --jq '.[0].number' 2> /dev/null)" || issue=""
  case "$issue" in
    "" | *[!0-9]*) issue="" ;;
  esac
  if [ -z "$issue" ] || ! gh_limited issue edit "$issue" --body "last run: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
exit code: $1
run_id: ${run_id:-none}" > /dev/null 2>&1; then
    log "wrapper: heartbeat not sent"
  fi
}

cleanup() {
  stop_group
  [ -z "$OUT" ] || rm -f "$OUT"
}

# Every exit from here on (setup failure, agent exit, time limit, a signal)
# cleans up, then pings, then exits with the run's own code. A second signal
# during this must not skip the ping, so signals are ignored from here.
on_exit() {
  local code=$?
  trap '' INT TERM HUP
  cleanup
  heartbeat "$code"
  exit "$code"
}
trap on_exit EXIT
trap 'exit 1' INT TERM HUP

mkdir -p "$LOG_DIR" || exit 2
OUT="$(mktemp "${TMPDIR:-/tmp}/po-agent-run.XXXXXX")" || exit 2

log "=== $(date '+%Y-%m-%dT%H:%M:%S%z') macmini-run.sh $MODE $SITE ==="

setup_failed() { # $1 = the step that failed
  local line="wrapper: setup failed ($1), agent not run"
  log "$line"
  open_issue "no run_id" 2 "$line"
  exit 2
}
# enabled from config/<site>.toml on origin/main: prints true or false, or
# fails unless there is exactly one "enabled = true|false" line (a trailing
# comment allowed). Read from main, not the tag, so enabled = false stops the
# next run without a tag move (decisions, 9 Nov 2026, release pinning).
main_enabled() {
  local config value
  config="$(git show "origin/main:config/$SITE.toml")" || return 1
  [ "$(printf '%s\n' "$config" | grep -cE '^[[:space:]]*enabled[[:space:]]*=')" = 1 ] || return 1
  value="$(printf '%s\n' "$config" | sed -n -E \
    's/^[[:space:]]*enabled[[:space:]]*=[[:space:]]*(true|false)[[:space:]]*(#.*)?$/\1/p')"
  case "$value" in
    true | false) echo "$value" ;;
    *) return 1 ;;
  esac
}

# Their own output goes to launchd.log (the plist's StandardOutPath).
git fetch --force --prune --prune-tags origin || setup_failed "git fetch"
enabled="$(main_enabled)" || setup_failed "enabled on main"
if [ "$enabled" = false ]; then
  log "wrapper: enabled = false on main, agent not run"
  exit 0
fi
tag_sha="$(git rev-parse --verify --quiet 'refs/tags/production^{commit}')" ||
  setup_failed "production tag missing"
git checkout --quiet --detach "$tag_sha" || setup_failed "git checkout"
log "wrapper: running production $(printf '%.12s' "$tag_sha")"
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

run_id="$(sed -n 's/^RUN_SUMMARY {"run_id": "\([0-9]\{8\}T[0-9]\{6\}Z-[0-9a-f]\{4\}\)".*/\1/p' "$OUT" | tail -n 1)"
if [ "$code" -ne 0 ] || grep -q '^ALERT ' "$OUT"; then
  open_issue "${run_id:-no run_id}" "$code" "$note"
fi
exit "$code"
