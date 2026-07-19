# Trigger Matrix — Debugging sessions

Read this file when review classifies the current session as **Debugging** (error patterns, "fix" commits, investigation flow).

| Signal | Recommended skill | Priority |
|--------|------------------|----------|
| Root cause identified (save as gotcha) | mn:save | HIGH |
| Fix committed without regression tests | test-master | CRITICAL |
| Investigation log worth preserving | mn:session | MEDIUM |
| Similar bug solved before | mn:ask (before fixing, to recall prior solution) | MEDIUM |
| Fix touches known-fragile code | review, ce:review | HIGH |

Also check universal triggers in `triggers-universal.md`.
