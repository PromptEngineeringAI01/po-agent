#!/bin/bash
# Mac Mini wrapper for the PO Agent (docs/macmini-setup.md section 8).
#
#   scripts/macmini-run.sh <run|spike|decide-only> <test|live> [summit]
#
# The site is required, with no default (decisions, 10 Nov 2026, live
# profile): after go-live launchd runs `run live`. Only launchd or Joey runs
# it on live; Claude never does (CLAUDE.md Must never #3). A third argument
# names the client (task 9.15; SPEC.md -> Client 2, The separate run):
# without it the run is B1's, exactly as before there were two clients;
# `summit` passes --client summit. Any other client: a fixed line to
# runs.log, an alert issue, exit 2, nothing else run.
#
# 1. Release pinning (plan task 7.4): fetches origin (moved and deleted tags
#    too), reads enabled from config/<site>.toml on origin/main, and for
#    Summit also from config/clients/summit.toml (either false: a fixed line
#    to runs.log, exit 0, nothing else run), then checks out the production
#    tag's commit, detached. Only Joey moves that tag, by hand; this script
#    never creates, moves or pushes it. Then uv sync --locked and uv run
#    playwright install chromium. If any step fails, or enabled on main
#    isn't exactly one "enabled = true|false" line in each file read, the
#    agent doesn't run: a fixed line to runs.log, an alert issue, exit 2.
# 2. Runs the agent on that site (never --detailed-log) with a hard time
#    limit, in its own process group, and kills the whole group plus this
#    client's Playwright browsers when it ends or hits the limit, so nothing
#    overlaps the next run. Summit's browsers live in their own folder
#    (PLAYWRIGHT_BROWSERS_PATH), so one client's kill never reaches the
#    other client's run.
# 3. Appends a timestamp line and the agent's stdout to runs.log; its stderr
#    goes to /dev/null (a crash's text could quote page content).
# 4. On any ALERT line or a non-zero exit, opens a GitHub issue labelled
#    po-agent-alert whose body is only the ALERT lines, without any Note ID
#    (the repo is public; audit N4), and the exit code. runs.log keeps the
#    ALERT lines whole. Summit's titles say "summit"; B1's are unchanged.
# 5. B1 only: at the end of every run, whatever the exit code (a failed setup
#    and a killed agent too), pings: the body of the one open issue labelled
#    po-agent-heartbeat becomes the time, the exit code and the run_id. The
#    heartbeat workflow (.github/workflows/heartbeat.yml) opens an alert when
#    no ping arrives for 2 hours inside the schedule. A failed ping only logs
#    a fixed line; it never changes the exit code. Summit runs leave it
#    alone, so it keeps meaning "B1 ran" (plan Phase S, open question 4).
# 6. Then, every run too, pings the client's own Healthchecks.io check
#    (decisions, 19 Nov 2026), whose URL is in poagent's Keychain;
#    Healthchecks.io emails Joey when a scheduled run doesn't ping. No URL,
#    or a failed ping, only logs a fixed line; it never changes the exit
#    code. A Summit run never pings B1's check, nor B1's run Summit's.
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
  echo "usage: macmini-run.sh <run|spike|decide-only> <test|live> [summit]" >&2
  exit 2
}

[ "$#" -eq 2 ] || [ "$#" -eq 3 ] || usage
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
CLIENT=b1
CLIENT_KNOWN=1
if [ "$#" -eq 3 ]; then
  case "$3" in
    summit) CLIENT=summit ;;
    *) CLIENT_KNOWN=0 ;; # refused below, once the log and alert work
  esac
fi
# Per client: the agent's --client, the alert title, the Healthchecks item,
# the browsers folder and the pattern that finds this client's browsers.
# B1's are exactly what they were before there were two clients.
if [ "$CLIENT" = summit ]; then
  AGENT_ARGS="$AGENT_ARGS --client summit"
  TITLE_PREFIX="po-agent alert summit"
  HC_ITEM=healthchecks_ping_url_summit
  HC_URL_ENV="${PO_AGENT_HEALTHCHECKS_PING_URL_SUMMIT:-}"
  PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright-summit"
  export PLAYWRIGHT_BROWSERS_PATH
  BROWSERS='ms-playwright-summit/'
  HEADER="$MODE $SITE summit"
else
  TITLE_PREFIX="po-agent alert"
  HC_ITEM=healthchecks_ping_url
  HC_URL_ENV="${PO_AGENT_HEALTHCHECKS_PING_URL:-}"
  BROWSERS='ms-playwright/' # not ms-playwright-summit/: Summit's are its own
  HEADER="$MODE $SITE"
fi
OUT=""
AGENT_PID=""
KEEP_BROWSERS=0 # 1: the agent skipped, another run holds the run lock
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
  [ -n "$OUT" ] || return 0
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
  if ! gh_limited issue create --label po-agent-alert --title "$TITLE_PREFIX $1" \
    --body "$body" > /dev/null 2>&1; then
    log "wrapper: alert issue not opened"
  fi
}

# Stops the agent's process group: SIGTERM, then SIGKILL after GRACE_S.
# Playwright starts Chromium detached (its own process group), so the group
# kill can't reach it: then every Playwright browser of this client is
# killed (B1's under ms-playwright/, Summit's under ms-playwright-summit/),
# never the other client's, whose run may be going on now.
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
  # Not when the agent skipped for the run lock: the browsers then belong to
  # the run that holds it (decisions, 21 Nov 2026, run lock).
  if [ "$KEEP_BROWSERS" -eq 0 ] &&
    pkill -KILL -u "$(id -u)" -f "$BROWSERS" 2> /dev/null; then
    log "wrapper: leftover Playwright browser killed"
  fi
  return 0
}

# The ping (step 5), B1's runs only. gh finds the repo from this checkout's
# remote, as for the alert issue. No PO data: only the time, $1 (the exit
# code) and run_id.
heartbeat() {
  local issue
  [ "$CLIENT" = b1 ] || return 0
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

# The Healthchecks.io ping (step 6; decisions, 19 Nov 2026): a plain GET of
# the client's check's ping URL, whatever the exit code (failed runs already
# open an alert issue). The URL is a secret: from PO_AGENT_HEALTHCHECKS_PING_URL
# (B1) or PO_AGENT_HEALTHCHECKS_PING_URL_SUMMIT (Summit; the tests), else
# poagent's login Keychain (service po-agent, the store keyring uses), item
# healthchecks_ping_url or healthchecks_ping_url_summit. It goes to curl as
# config on stdin, so it is never in the process list, and curl's output goes
# nowhere, so it never reaches a log. curl's own limits (20 s an attempt, 2
# retries, no retry after 40 s) keep a hung network from holding the wrapper.
healthchecks_ping() {
  local url="$HC_URL_ENV"
  if [ -z "$url" ]; then
    url="$(security find-generic-password -s po-agent -a "$HC_ITEM" \
      -w 2> /dev/null)" || url=""
  fi
  case "$url" in
    *'"'* | *'\'* | *[[:space:]]*) # would break the curl config line
      log "wrapper: healthchecks ping not sent"
      return 0
      ;;
    https://*) ;;
    "")
      log "wrapper: healthchecks ping not configured"
      return 0
      ;;
    *)
      log "wrapper: healthchecks ping not sent"
      return 0
      ;;
  esac
  if ! printf 'url = "%s"\n' "$url" |
    curl -fsS -m 20 --retry 2 --retry-max-time 40 -o /dev/null -K - \
      > /dev/null 2>&1; then
    log "wrapper: healthchecks ping not sent"
  fi
}

cleanup() {
  stop_group
  [ -z "$OUT" ] || rm -f "$OUT"
}

mkdir -p "$LOG_DIR" || exit 2

# An unknown client: no client's run, so no client's ping either.
if [ "$CLIENT_KNOWN" -eq 0 ]; then
  line="wrapper: unknown client, agent not run"
  log "=== $(date '+%Y-%m-%dT%H:%M:%S%z') macmini-run.sh $MODE $SITE ? ==="
  log "$line"
  open_issue "no run_id" 2 "$line"
  exit 2
fi

# Every exit from here on (setup failure, agent exit, time limit, a signal)
# cleans up, then pings, then exits with the run's own code. A second signal
# during this must not skip the ping, so signals are ignored from here.
on_exit() {
  local code=$?
  trap '' INT TERM HUP
  cleanup
  heartbeat "$code"
  healthchecks_ping
  exit "$code"
}
trap on_exit EXIT
trap 'exit 1' INT TERM HUP

OUT="$(mktemp "${TMPDIR:-/tmp}/po-agent-run.XXXXXX")" || exit 2

log "=== $(date '+%Y-%m-%dT%H:%M:%S%z') macmini-run.sh $HEADER ==="

setup_failed() { # $1 = the step that failed
  local line="wrapper: setup failed ($1), agent not run"
  log "$line"
  open_issue "no run_id" 2 "$line"
  exit 2
}
# enabled from $1 (a config file) on origin/main: prints true or false, or
# fails unless there is exactly one "enabled = true|false" line (a trailing
# comment allowed). Read from main, not the tag, so enabled = false stops the
# next run without a tag move (decisions, 9 Nov 2026, release pinning).
main_enabled() {
  local config value
  config="$(git show "origin/main:$1")" || return 1
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
enabled="$(main_enabled "config/$SITE.toml")" || setup_failed "enabled on main"
# Summit also needs its client file's switch (SPEC.md -> The separate run).
if [ "$CLIENT" = summit ] && [ "$enabled" = true ]; then
  enabled="$(main_enabled "config/clients/summit.toml")" ||
    setup_failed "enabled on main"
fi
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
  if grep -qx 'INFO  run lock held: run not started' "$OUT"; then
    KEEP_BROWSERS=1
  fi
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
