#!/usr/bin/env bash
# Save an observation to claude-mem with embedded provenance.
# Usage: claude-mem-save.sh <url> <type> <project> <summary> [note_name] [vault]
#
# claude-mem v12.3.9 gotcha (encoded here so the caller doesn't reproduce it by hand):
#   - the payload key is "text", NOT "content";
#   - metadata.project is silently dropped over HTTP, so provenance is mirrored into text
#     to keep pre/post-v12 filtering working. Details: references/gotchas.md.
set -u  # NOT -e -o pipefail: a missing plugin cache must not kill the script (graceful, like check-cm-version.sh)

URL="${1:?url required}"
TYPE="${2:?type required}"
PROJECT="${3:?project required}"
SUMMARY="${4:?summary required}"
NOTE="${5:-}"
VAULT="${6:-}"

# Auto-detect the claude-mem version (provenance — separate pre-v12 from post-v12 data).
# Guard like check-cm-version.sh: no cache -> "unknown", never abort (claude-mem may not be installed).
CACHE="$HOME/.claude/plugins/cache/thedotmack/claude-mem"
CM_VERSION="unknown"
[ -d "$CACHE" ] && CM_VERSION=$(ls -1 "$CACHE" 2>/dev/null | sort -V | tail -1)
CM_VERSION="${CM_VERSION:-unknown}"

# Build the JSON via python3 — robust escaping (summary/note may carry quotes, $(...), backticks).
PAYLOAD=$(python3 - "$SUMMARY" "$NOTE" "$VAULT" "$CM_VERSION" "$TYPE" "$PROJECT" <<'PY'
import json, sys
summary, note, vault, cmv, typ, project = sys.argv[1:7]
text = f"{summary} [note: {note or '—'} | vault: {vault or '—'} | cm: {cmv}]"
print(json.dumps({
    "text": text,  # NOT "content" — v12.3.9 gotcha
    "metadata": {
        "type": typ,
        "project": project,          # dropped over HTTP, but kept for local paths
        "obsidian_note": note,
        "obsidian_vault": vault,
        "claude_mem_version": cmv,
    },
}, ensure_ascii=False))
PY
)

curl -s -X POST "${URL%/}/api/memory/save" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
