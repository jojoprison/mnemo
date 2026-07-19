# Trigger Matrix — Universal (all session types)

Read this file for triggers that apply regardless of session type — classified or not. Always cross-reference with the type-specific trigger file.

| Signal | Recommended skill | Priority |
|--------|------------------|----------|
| Significant work done, no session notes | mn:session | HIGH |
| Decisions in conversation, not persisted | mn:save | HIGH |
| Uncommitted changes in working tree | commit | CRITICAL |
| Branch ready, no PR created | ship | HIGH |
| Project has memory routing rules (CLAUDE.md) | check all memory backends | MEDIUM |
| New Obsidian notes created this session | mn:connect, mn:health | LOW |
| Plan created but not reviewed | plan-eng-review, plan-ceo-review | MEDIUM |
| Code written, no review pass | review, ce:review | MEDIUM |
| CLAUDE.md needs updating | claude-md-management:revise-claude-md | LOW |

## Refactoring / Documentation / Configuration / Planning sessions

These types are lighter and mostly covered by Universal triggers. Specific notes:

- **Refactoring**: large diffs with net-zero line changes. Watch for `simplify` and `review` triggers.
- **Documentation**: .md files dominant. Watch for `mn:health` (if you created many notes) and `document-release` (if post-ship).
- **Configuration**: CI/deploy/settings files. Watch for `ship` if the config is deployable.
- **Planning**: plan mode, brainstorm docs. Watch for `plan-eng-review` + `plan-ceo-review` if no review done.
