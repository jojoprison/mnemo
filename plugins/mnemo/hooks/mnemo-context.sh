#!/usr/bin/env bash
# SessionStart nudge — remind the agent that mnemo memory exists, so it reaches for
# the ask and save skills on its own initiative rather than only on an explicit command.
#
# Deterministic DELIVERY (a hook always fires) ≠ deterministic EFFECT (the model still
# decides whether to call the skill). This is a short, factual nudge — not an order.
#
# Gated: prints context only if mnemo is configured (vault set) AND hooks.sessionStartNudge != false.
# Otherwise silent. Never blocks, exit 0 always.
set -u

CONFIG="${HOME}/.mnemo/config.json"
is_codex_runtime() {
  [ -n "${PLUGIN_ROOT:-}${CODEX_THREAD_ID:-}${CODEX_SESSION_ID:-}" ]
}
silent() {
  if is_codex_runtime; then
    echo '{"continue":true}'
  else
    echo '{"continue":true,"suppressOutput":true}'
  fi
  exit 0
}

[ -f "$CONFIG" ] || silent

if is_codex_runtime; then
  RUNTIME="codex"
else
  RUNTIME="claude"
fi

OUT=$(python3 - "$CONFIG" "$RUNTIME" <<'PY' 2>/dev/null
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
# Gate: hooks.sessionStartNudge defaults to true.
if cfg.get("hooks", {}).get("sessionStartNudge", True) is False:
    sys.exit(1)
vault = cfg.get("vault", "")
if not vault:
    sys.exit(1)
is_codex = sys.argv[2] == "codex"
ask = "$mnemo:ask" if is_codex else "/mn:ask"
save = "$mnemo:save" if is_codex else "/mn:save"
msg = (
    f"mnemo memory is set up here (vault: {vault}). Reach for it on your own initiative, "
    f"not only when asked: before non-trivial work, recall prior context with {ask} "
    "(especially before re-fixing a recurring bug or touching an unfamiliar area); "
    f"capture findings, decisions, and gotchas as they happen with {save} so a future "
    "session doesn't relearn them."
)
payload = {
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": msg,
    }
}
print(json.dumps(payload, ensure_ascii=False))
PY
)

[ -n "$OUT" ] && echo "$OUT" || silent
