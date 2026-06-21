#!/usr/bin/env bash
# Return the filesystem path of an Obsidian vault.
# Usage: get-vault-path.sh [vault-name]  (defaults to "main")
#
# Output: single line with the absolute path, or empty string if unavailable.
# Exit code: 0 on success (even if empty), 1 only on fatal error.

set -u

VAULT="${1:-main}"
# Output is tab-separated ("path<TAB>/abs/path"). Match the literal field name and
# split on TAB — NOT `\s`, which macOS/BSD awk does not support (it silently matches
# nothing → empty path even when Obsidian is running). -F'\t' also preserves spaces in paths.
obsidian vault vault="$VAULT" 2>/dev/null | awk -F'\t' '$1=="path"{print $2; exit}'
