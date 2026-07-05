#!/usr/bin/env bash
# Сохранить observation в claude-mem с встроенным провенансом.
# Usage: claude-mem-save.sh <url> <type> <project> <summary> [note_name] [vault]
#
# Гоча claude-mem v12.3.9 (закодирована здесь, чтобы вызывающий её не воспроизводил руками):
#   - поле полезной нагрузки — "text", НЕ "content";
#   - metadata.project молча дропается при HTTP-вызове → провенанс дублируется в text,
#     чтобы фильтрация pre/post-v12 работала. Детали: references/gotchas.md.
set -euo pipefail

URL="${1:?url required}"
TYPE="${2:?type required}"
PROJECT="${3:?project required}"
SUMMARY="${4:?summary required}"
NOTE="${5:-}"
VAULT="${6:-}"

# Автодетект версии claude-mem (для провенанса — отделить pre-v12 данные от post-v12).
CM_VERSION=$(ls -1 ~/.claude/plugins/cache/thedotmack/claude-mem/ 2>/dev/null | sort -V | tail -1)
CM_VERSION="${CM_VERSION:-unknown}"

# Сборка JSON через python3 — надёжное экранирование (summary/note могут нести кавычки, $(...), бэктики).
PAYLOAD=$(python3 - "$SUMMARY" "$NOTE" "$VAULT" "$CM_VERSION" "$TYPE" "$PROJECT" <<'PY'
import json, sys
summary, note, vault, cmv, typ, project = sys.argv[1:7]
text = f"{summary} [note: {note or '—'} | vault: {vault or '—'} | cm: {cmv}]"
print(json.dumps({
    "text": text,  # НЕ "content" — гоча v12.3.9
    "metadata": {
        "type": typ,
        "project": project,          # дропается по HTTP, но пусть будет для локальных путей
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
