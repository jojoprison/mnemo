#!/usr/bin/env bash
# UserPromptExpansion echo — visible confirmation that a /mn:* slash command expanded
# into its skill body. Deterministic DELIVERY (the hook always fires), unlike the
# in-body invocation marker which relies on model compliance.
#
# Claude Code only: Codex never emits this event, and legacy Codex hook parsers
# ignore unknown event sections in hooks.json — a guaranteed no-op there.
# Empirics (CC 2.1.215, live capture): fires for plugin slash commands with
# {command_name: "mn:health", command_source: "plugin", expansion_type: "slash_command"};
# hook stdout never alters the expansion, so a malformed reply cannot break skills.
#
# Gated by hooks.invocationEcho (default true; missing config = on — the echo confirms
# skill loading and does not depend on a vault). Never blocks, exit 0 always.
set -u

PAYLOAD=$(cat 2>/dev/null || true)

OUT=$(PAYLOAD="$PAYLOAD" python3 - "${HOME}/.mnemo/config.json" <<'PY' 2>/dev/null
import json, os, sys

try:
    data = json.loads(os.environ.get("PAYLOAD", "") or "{}")
except Exception:
    sys.exit(1)
command = str(data.get("command_name", ""))
if not command.startswith("mn:"):
    sys.exit(1)
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    cfg = {}
if cfg.get("hooks", {}).get("invocationEcho", True) is False:
    sys.exit(1)
print(json.dumps({
    "continue": True,
    "systemMessage": f"🧠 mnemo: /{command} → skill body loaded",
}, ensure_ascii=False))
PY
)

if [ -n "$OUT" ]; then
  echo "$OUT"
else
  echo '{"continue":true,"suppressOutput":true}'
fi
exit 0
