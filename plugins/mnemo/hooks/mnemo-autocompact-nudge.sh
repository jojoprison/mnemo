#!/usr/bin/env bash
# Autocompact nudge — warn before Claude Code silently compacts the context
# window, so the agent saves the session (/mn:review --full) while it can
# still remember what happened.
#
# Claude Code only: the autocompact window this hook protects against is a
# Claude Code mechanism, so it no-ops on Codex (see docs/design-decisions.md,
# "Proactive nudges via hooks").
#
# Safety design (mirrors hooks/mnemo-stop-nudge.sh):
#   - Config-gated: hooks.autocompactNudge defaults to FALSE. A blocking Stop
#     hook only runs when the user opts in. The default install never blocks.
#   - Threshold is a FIXED margin from the window (W - N), not a fraction of
#     it — any hardcoded per-model window table would be wrong for someone
#     (windows range 200k-1M), so W is resolved only from sources Claude Code
#     itself already resolved (env / settings / its own cache). Unknown W
#     means silence, never a guess.
#   - Anti-loop governor: a private hashed marker stores the highest severity
#     already nudged this session, so it blocks at most once entering "warn"
#     and once entering "critical" — never once per Stop.
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

is_codex_runtime && pass

INPUT=$(cat 2>/dev/null || true)
[ -f "$CONFIG" ] || pass

# Gate: opt-in only (default false), same posture as hooks.stopNudge.
EN=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('hooks',{}).get('autocompactNudge',False))" "$CONFIG" 2>/dev/null || echo False)
[ "$EN" = "True" ] || pass

IFS=$'\t' read -r SESSION TRANSCRIPT STOP_ACTIVE < <(
  printf '%s' "$INPUT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('session_id','unknown'),d.get('transcript_path',''),int(bool(d.get('stop_hook_active'))),sep='\t')" 2>/dev/null \
    || printf 'unknown\t\t0\n'
)
[ "${STOP_ACTIVE:-0}" = 1 ] && pass
[ -f "$TRANSCRIPT" ] || pass

MNEMO_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}}"

IFS=$'\t' read -r LEVEL USED WINDOW < <(
  python3 "$MNEMO_ROOT/scripts/context-window.py" "$TRANSCRIPT" 2>/dev/null
)
LEVEL="${LEVEL:-unknown}"
[ "$LEVEL" = "unknown" ] && pass
[ "$LEVEL" = "none" ] && pass

# Anti-loop marker lives in the same private, hashed cache namespace as
# stop-nudge's, keyed on session_id (falls back to CODEX_THREAD_ID — moot
# here since Codex already exited above, but keeps the key derivation
# identical to the template this hook is modeled on).
if [ -z "${SESSION:-}" ] || [ "$SESSION" = "unknown" ]; then
  SESSION="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-unknown}}"
fi
MARKER=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import cache_path;p=cache_path("autocompact-nudged",sys.argv[2],"marker");print(p or "")' "$MNEMO_ROOT/scripts" "$SESSION" 2>/dev/null || true)
[ -n "$MARKER" ] || pass
PRIOR=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import read_text;t=read_text(__import__("pathlib").Path(sys.argv[2]));print(t or "none")' "$MNEMO_ROOT/scripts" "$MARKER" 2>/dev/null || echo none)

rank() { case "$1" in critical) echo 2 ;; warn) echo 1 ;; *) echo 0 ;; esac; }
[ "$(rank "$LEVEL")" -le "$(rank "$PRIOR")" ] && pass

MARKER_WRITTEN=$(python3 -c 'import sys;sys.path.insert(0,sys.argv[1]);from cache_utils import atomic_write_text;from pathlib import Path;print(atomic_write_text(Path(sys.argv[2]),sys.argv[3]))' "$MNEMO_ROOT/scripts" "$MARKER" "$LEVEL" 2>/dev/null || echo False)
# Fail open if the anti-loop governor cannot be persisted. Blocking without a
# marker could trap the user in a repeated Stop cycle.
[ "$MARKER_WRITTEN" = "True" ] || pass

if [ "$LEVEL" = "critical" ]; then
  URGENCY="This session is very close to Claude Code's autocompact window"
else
  URGENCY="This session is approaching Claude Code's autocompact window"
fi
MSG="${URGENCY} (~${USED} of ${WINDOW} tokens used). Autocompact will summarize the session and drop raw context. Close it out now with /mn:review --full — it audits, saves the facts, writes the session note + handoff, and links them — before that happens. Then stop again to proceed."
python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1]}, ensure_ascii=False))" "$MSG"
