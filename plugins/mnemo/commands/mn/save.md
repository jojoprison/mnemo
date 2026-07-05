---
name: mn:save
description: "Routing cascade — a recall item to Obsidian + claude-mem + memory/, or an actionable rule (never-X / always-Y tied to code) to .claude/rules/, with graceful degradation."
user-invocable: true
disable-model-invocation: true
---

$ARGUMENTS

Invoke the save skill: use the Skill tool with skill: "mnemo:memory-routing", args: "$ARGUMENTS"
