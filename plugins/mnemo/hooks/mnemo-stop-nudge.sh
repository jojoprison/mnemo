#!/usr/bin/env bash
# Stop nudge — if the session produced fixes/decisions worth keeping but save and/or
# session never ran, block the stop ONCE with a reason listing what's still missing,
# so the agent wraps up cleanly (save pins discrete facts; session writes the narrative + handoff).
#
# Safety design (a public plugin must not trap arbitrary users in a loop):
#   - Config-gated: hooks.stopNudge defaults to FALSE. A blocking Stop hook only runs when
#     the user opts in. The default install never blocks.
#   - Anti-loop governor: blocks at most ONCE per session (a private hashed marker);
#     the second Stop passes through, so the agent is never stuck.
#   - Governor conditions: silent unless worth-saving signals are present AND at least one of
#     /mn:save / /mn:session was not invoked this session.
set -u

CONFIG="${HOME}/.mnemo/config.json"
is_codex_runtime() {
  [ -n "${PLUGIN_ROOT:-}${CODEX_THREAD_ID:-}${CODEX_SESSION_ID:-}" ]
}
pass() {
  if is_codex_runtime; then
    echo '{"continue":true}'
  else
    echo '{"continue":true,"suppressOutput":true}'
  fi
  exit 0
}

INPUT=$(cat 2>/dev/null || true)
[ -f "$CONFIG" ] || pass

# Gate: opt-in only (default false).
EN=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('hooks',{}).get('stopNudge',False))" "$CONFIG" 2>/dev/null || echo False)
[ "$EN" = "True" ] || pass

# Read session_id + transcript_path from the hook stdin payload. The official
# recursion flag is an independent guard even if the private marker is missing.
IFS=$'\t' read -r SESSION TRANSCRIPT STOP_ACTIVE < <(
  printf '%s' "$INPUT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('session_id','unknown'),d.get('transcript_path',''),int(bool(d.get('stop_hook_active'))),sep='\t')" 2>/dev/null \
    || printf 'unknown\t\t0\n'
)
[ "${STOP_ACTIVE:-0}" = 1 ] && pass
[ -f "$TRANSCRIPT" ] || pass

# Reuse the structured transcript parser. Raw grep would mistake docs, AGENTS,
# code, or tool output containing command names for actual skill invocations.
MNEMO_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}}"

# Anti-loop marker lives in the same private, hashed cache namespace as helpers.
MARKER=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import cache_path;p=cache_path("stop-nudged",sys.argv[2],"marker");print(p or "")' "$MNEMO_ROOT/scripts" "$SESSION" 2>/dev/null || true)
[ -n "$MARKER" ] || pass
MARKED=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import read_text;print(read_text(__import__("pathlib").Path(sys.argv[2])) is not None)' "$MNEMO_ROOT/scripts" "$MARKER" 2>/dev/null || echo False)
[ "$MARKED" = "True" ] && pass

read -r SAVED SESSIONED SIGNALS < <(
  python3 "$MNEMO_ROOT/scripts/session-scan.py" --stop-summary "$TRANSCRIPT" 2>/dev/null
)
SAVED="${SAVED:-0}"
SESSIONED="${SESSIONED:-0}"
SIGNALS="${SIGNALS:-0}"

# Both already ran → nothing to nudge.
[ "$SAVED" = 1 ] && [ "$SESSIONED" = 1 ] && pass

# Worth-saving signals threshold (both EN + RU markers).
[ "${SIGNALS:-0}" -lt 3 ] 2>/dev/null && pass

# Build the list of what's still missing (save pins discrete facts; session writes the narrative + handoff).
if is_codex_runtime; then
  SAVE_CMD='$mnemo:save'
  SESSION_CMD='$mnemo:session'
else
  SAVE_CMD='/mn:save'
  SESSION_CMD='/mn:session'
fi
MISSING=""
[ "$SAVED" = 0 ] && MISSING="$SAVE_CMD"
[ "$SESSIONED" = 0 ] && MISSING="${MISSING:+$MISSING and }$SESSION_CMD"

MARKER_WRITTEN=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import atomic_write_text;from pathlib import Path;print(atomic_write_text(Path(sys.argv[2]),"1"))' "$MNEMO_ROOT/scripts" "$MARKER" 2>/dev/null || echo False)
# Fail open if the anti-loop governor cannot be persisted. Blocking without a
# marker could trap the user in a repeated Stop cycle.
[ "$MARKER_WRITTEN" = "True" ] || pass
MSG="This session looks like it produced fixes or decisions worth keeping. Before wrapping up, run: ${MISSING}. Then stop again to proceed."
python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1]}, ensure_ascii=False))" "$MSG"
