#!/usr/bin/env bash
# Prewarm review caches so the first mnemo review in a session is instant.
# Codex skips async hook handlers, so this manifest handler is synchronous.
# At SessionStart the transcript is tiny; both warmers fail open and stay cheap.

set -euo pipefail

CODEX_HOOK=0
[ -n "${PLUGIN_ROOT:-}" ] && CODEX_HOOK=1
PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}}"
SCRIPTS_DIR="${PLUGIN_ROOT}/scripts"
INPUT=$(cat 2>/dev/null || true)
SESSION_ID=$(printf '%s' "$INPUT" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("session_id", ""))' 2>/dev/null || true)

# Codex guarantees PLUGIN_ROOT and hook stdin, but not CODEX_THREAD_ID. Claude
# exposes CLAUDE_PLUGIN_ROOT. Normalize the stdin session id for helper discovery.
if [ "$CODEX_HOOK" = 1 ]; then
  export CODEX_THREAD_ID="${CODEX_THREAD_ID:-$SESSION_ID}"
elif [ -n "$SESSION_ID" ]; then
  export CLAUDE_SESSION_ID="${CLAUDE_SESSION_ID:-$SESSION_ID}"
fi

# Fail silently — prewarm is best-effort, never blocks the session.
[ -d "$SCRIPTS_DIR" ] || exit 0

python3 "$SCRIPTS_DIR/skills-discover.py" </dev/null >/dev/null 2>&1 || true
if [ -n "${CLAUDE_SESSION_ID:-}${CODEX_THREAD_ID:-}${CODEX_SESSION_ID:-}${SESSION_ID:-}" ]; then
  python3 "$SCRIPTS_DIR/session-scan.py" </dev/null >/dev/null 2>&1 || true
fi
exit 0
