#!/usr/bin/env bash
# Inspect the installed claude-mem plugin cache.
#
# Outputs three lines:
#   version: <latest version folder, or empty>
#   stale:   <number of version folders minus 1 — >0 means restart Claude windows>
#   path:    <path to cache root, or empty if not installed>
#
# Exit code: 0 always (missing plugin is not an error — just empty output).

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/claude-mem-save.py" --probe
