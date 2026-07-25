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

# Project label for the open-tails digest. Use the git COMMON dir, not the
# worktree root: in a worktree `basename $(git rev-parse --show-toplevel)` is the
# worktree's name (floating-frolicking-goose), not the project's (mnemo).
PROJECT=""
if command -v git >/dev/null 2>&1; then
  COMMON_DIR=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
  [ -n "$COMMON_DIR" ] && PROJECT=$(basename "$(dirname "$COMMON_DIR")")
fi

PLUGIN_DIR="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"

OUT=$(python3 - "$CONFIG" "$RUNTIME" "$PLUGIN_DIR" "$PROJECT" <<'PY' 2>/dev/null
import json, os, subprocess, sys
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


def hot_digest() -> str:
    """Open tails from recent session notes — the forward-state half of memory.

    Best-effort and byte-capped: any failure (no Obsidian, no plugin root, slow
    CLI) yields an empty string, so the nudge above is never lost to it.
    Gate: hooks.hotDigest, defaults to true.
    """
    if cfg.get("hooks", {}).get("hotDigest", True) is False:
        return ""
    plugin_root = sys.argv[3] if len(sys.argv) > 3 else ""
    script = os.path.join(plugin_root, "scripts", "hot-scan.py")
    if not plugin_root or not os.path.isfile(script):
        return ""
    try:
        probe = subprocess.run(
            ["obsidian", "vault", f"vault={vault}"],
            capture_output=True, text=True, timeout=3, check=False)
    except Exception:
        return ""
    vault_path = ""
    for line in probe.stdout.splitlines():
        field, separator, value = line.partition("\t")
        if field == "path" and separator and value:
            vault_path = value
            break
    if not vault_path or not os.path.isdir(vault_path):
        return ""
    command = [sys.executable, script, vault_path]
    project = sys.argv[4] if len(sys.argv) > 4 else ""
    # Project scope keeps the digest about the repo in front of you; "all" is
    # for people who want the cross-project view every session.
    if cfg.get("hot", {}).get("scope", "project") == "project" and project:
        command += ["--project", project]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=5, check=False)
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


digest = hot_digest()
if digest:
    msg = f"{msg}\n\n{digest}"
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
