#!/usr/bin/env bash
# SessionStart nudge — remind the agent that mnemo memory exists, so it reaches for
# /mn:ask and /mn:save on its own initiative rather than only on an explicit command.
#
# Deterministic DELIVERY (a hook always fires) ≠ deterministic EFFECT (the model still
# decides whether to call the skill). This is a short, factual nudge — not an order.
#
# Gated: prints context only if mnemo is configured (vault set) AND hooks.sessionStartNudge != false.
# Otherwise silent. Never blocks, exit 0 always.
set -u

CONFIG="${HOME}/.mnemo/config.json"
silent() { echo '{"continue":true,"suppressOutput":true}'; exit 0; }

[ -f "$CONFIG" ] || silent

OUT=$(python3 - "$CONFIG" <<'PY' 2>/dev/null
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
msg = (
    f"mnemo memory is set up here (vault: {vault}). Reach for it on your own initiative, "
    "not only when asked: before non-trivial work, recall prior context with /mn:ask "
    "(especially before re-fixing a recurring bug or touching an unfamiliar area); "
    "capture findings, decisions, and gotchas as they happen with /mn:save so a future "
    "session doesn't relearn them."
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": msg}}, ensure_ascii=False))
PY
)

[ -n "$OUT" ] && echo "$OUT" || silent
