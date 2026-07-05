#!/usr/bin/env bash
# Stop nudge — if the session produced fixes/decisions worth keeping but /mn:save and/or
# /mn:session never ran, block the stop ONCE with a reason listing what's still missing,
# so the agent wraps up cleanly (save pins discrete facts; session writes the narrative + handoff).
#
# Safety design (a public plugin must not trap arbitrary users in a loop):
#   - Config-gated: hooks.stopNudge defaults to FALSE. A blocking Stop hook only runs when
#     the user opts in. The default install never blocks.
#   - Anti-loop governor: blocks at most ONCE per session (a /tmp marker keyed by session_id);
#     the second Stop passes through, so the agent is never stuck.
#   - Governor conditions: silent unless worth-saving signals are present AND at least one of
#     /mn:save / /mn:session was not invoked this session.
set -u

CONFIG="${HOME}/.mnemo/config.json"
pass() { echo '{"continue":true,"suppressOutput":true}'; exit 0; }

INPUT=$(cat 2>/dev/null || true)
[ -f "$CONFIG" ] || pass

# Gate: opt-in only (default false).
EN=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('hooks',{}).get('stopNudge',False))" "$CONFIG" 2>/dev/null || echo False)
[ "$EN" = "True" ] || pass

# Read session_id + transcript_path from the hook stdin payload.
read -r SESSION TRANSCRIPT < <(printf '%s' "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id','unknown'), d.get('transcript_path',''))" 2>/dev/null || echo "unknown ")
[ -f "$TRANSCRIPT" ] || pass

# Anti-loop: already nudged this session → let it stop.
MARKER="/tmp/mnemo-stop-nudged-${SESSION}"
[ -f "$MARKER" ] && pass

# What's already been done this session — track BOTH the discrete save and the session note.
grep -qE "mnemo:memory-routing|mn:save" "$TRANSCRIPT" 2>/dev/null && SAVED=1 || SAVED=0
grep -qE "mnemo:session-notes|mn:session" "$TRANSCRIPT" 2>/dev/null && SESSIONED=1 || SESSIONED=0

# Both already ran → nothing to nudge.
[ "$SAVED" = 1 ] && [ "$SESSIONED" = 1 ] && pass

# Worth-saving signals threshold (both EN + RU markers).
# grep -c already prints 0 on no match (and exits 1) → `|| true` keeps just "0", no double value.
SIGNALS=$(grep -ciE "fixed|solved|resolved|root cause|decided|gotcha|починил|решил|разобрал|決定" "$TRANSCRIPT" 2>/dev/null || true)
[ "${SIGNALS:-0}" -lt 3 ] 2>/dev/null && pass

# Build the list of what's still missing (save pins discrete facts; session writes the narrative + handoff).
MISSING=""
[ "$SAVED" = 0 ] && MISSING="/mn:save"
[ "$SESSIONED" = 0 ] && MISSING="${MISSING:+$MISSING and }/mn:session"

touch "$MARKER" 2>/dev/null || true
MSG="This session looks like it produced fixes or decisions worth keeping. Before wrapping up, run: ${MISSING}. Then stop again to proceed."
python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1]}, ensure_ascii=False))" "$MSG"
