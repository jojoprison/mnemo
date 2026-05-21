# mnemo

> Persistent memory layer for Codex and Claude Code — your Obsidian vault on autopilot.

[![Codex](https://img.shields.io/badge/Codex-skills-black?style=flat-square)](https://developers.openai.com/codex/skills)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-blueviolet?style=flat-square)](https://claude.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Skills](https://img.shields.io/badge/Skills-8-blue?style=flat-square)](plugins/mnemo/skills/)
[![Obsidian](https://img.shields.io/badge/Obsidian-compatible-7C3AED?style=flat-square&logo=obsidian&logoColor=white)](https://obsidian.md)

**[English](#-what-it-does)** | **[Русский](#-что-делает)** | **[中文](#-功能介绍)**

---

## What It Does

**mnemo** gives Codex and Claude Code a persistent memory through your Obsidian vault. Eight skills handle the boring parts of knowledge management so you can focus on thinking.

Most "second brain" tools assume you have time to organize. mnemo assumes you don't.

```
You work → mnemo remembers → Your vault grows → You find things later
```

### The Skills

| Skill | Command | What it does |
|-------|---------|-------------|
| **health** | `/mn:health` | Vault audit: orphans, broken links, missing sections, stale notes, growth stats |
| **ask** | `/mn:ask` | Search vault and synthesize answers from multiple notes with citations |
| **connect** | `/mn:connect` | Discover hidden connections between notes you'd never think of |
| **sort** | `/mn:sort` | Classify inbox notes into proper types (atom, molecule, source...) |
| **session** | `/mn:session` | Auto-generate session summary + cross-session handoff |
| **save** | `/mn:save` | Memory routing cascade — Obsidian + claude-mem + memory/ with graceful degradation |
| **review** | `/mn:review` | End-of-session orchestrator — auto-saves decisions, creates session notes, recommends remaining skills |
| **setup** | `/mn:setup` | Interactive onboarding — vault name, taxonomy, language |

### Why Not Just Use Obsidian Plugins?

Obsidian plugins run inside Obsidian. mnemo runs inside your coding agent — **Codex or Claude Code** — so it has access to your development context, conversation history, and codebase. When you finish a 3-hour debugging session, `mnemo:session-notes` knows what you did because it was there.

### What's New in v0.7.3

**Hybrid fork/inherit routing — no more `Extra usage required for 1M context` 429s.** v0.6.0's tiered `model:` overrides were forcing a mid-session model switch on every skill invocation, which re-reads the full conversation without cache. On Max plans (where Opus auto-upgrades to 1M context), a big conversation + a switch tripped Anthropic's server-side 1M billing gate and failed with `API Error: Extra usage is required for 1M context`.

**The fix** splits skills by whether they need session context:

- **4 skills run forked** (`context: fork` + concrete model) — `/mn:health`, `/mn:connect`, `/mn:sort`, `/mn:setup`. Isolated subagents with their own 200K context, no impact on the main session.
- **4 skills inherit** (`model: inherit`) — `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review`. They use whatever model you picked via `/model` so you keep central control.

`/mn:review` gained a one-line tip: *"run `/model opus[1m]` before review for deepest analysis."* Keeps the cheap default without losing the previous forced-opus ceiling. Linter extended to accept `model: inherit` and `context: fork`, rejects the contradictory `fork + inherit` combination.

### What's New in v0.7.2

**CI lint for SKILL.md files.** `scripts/lint-skills.py` validates frontmatter, model whitelist, line budget, and every `references/` / `scripts/` / `assets/` path mentioned in a skill. Runs on every push via `.github/workflows/skill-lint.yml`. Catches broken references after renames, stale script pointers, accidental `model: opus-42`, oversized skills. Run locally with `python3 scripts/lint-skills.py`.

**`/mn:session` template actually loads.** Step 3 now explicitly `cat`s `assets/session-template.md` before filling placeholders — the template was referenced but never read before.

**`/mn:review` triggers always load.** Step 4 now explicitly `cat`s `triggers-{type}.md` + `triggers-universal.md` + project-local `skill-triggers.md` (if present). No more relying on Claude to remember to read them.

**README "Project Structure" matches reality** — added `references/`, `assets/`, `hooks/`, `scripts/`, and CI workflow.

### What's New in v0.7.1

**Polish release driven by a skill-creator audit.** Removed ~100 lines of duplicated gotchas/config/tool-routing prose across 7 SKILL.md files by extracting to `plugins/mnemo/references/`. Skills now load the reference only when needed (progressive disclosure). `session-review` alone dropped 262 → 222 lines by splitting its huge trigger matrix into per-session-type files.

**Pushier descriptions** to stop Claude from under-triggering skills (this was a real concern flagged by skill-creator). Seven skills got Russian trigger phrases and proactive "use whenever" language.

**Incremental session scan.** `session-scan.py` now reads only appended JSONL bytes since the last scan. First `/mn:review` on a 5000-line session: ~200ms → ~20ms parse.

**`/mn:sort` bulk mode.** Say "accept all" to skip per-note confirmation.

**`/mn:setup` idempotent handoff.** Re-running setup no longer clobbers an existing handoff note.

### What's New in v0.7.0

**claude-mem v12.3.9 integration.** If you also run [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem), mnemo now talks to it:

- **`/mn:health` Step 0** surfaces stale-cache + major-version-skew warnings — the real-world failure mode where Stop hooks point to a deleted `CLAUDE_PLUGIN_ROOT` after `/plugin update`.
- **`/mn:save` Step 2** auto-detects `claude_mem_version` and tags every observation with `obsidian_note` + `obsidian_vault` backlinks. Groundwork for a future `/mn:ask --deep` mode that shows semantic-search hits next to their full vault note.

### What's New in v0.6.2

**`/mn:connect` does one grep instead of N `obsidian search` calls.** Single filesystem pass for all concepts OR'd into one regex. **7 concepts: 1.26s → 50ms (25x).**

**`/mn:health` Steps 1-4 run in parallel.** Orphans, unresolved, tags, files-count are independent CLI queries — documented as parallel batches. 720ms → 180ms.

**SessionStart prewarm hook.** `/mn:review` caches warm up async on session boot, so the **first** review is instant instead of ~10s.

### What's New in v0.6.1

**Model tiers, corrected against real benchmarks.** v0.6.0 was tiered by intuition. v0.6.1 rebalanced after reading Anthropic docs, Artificial Analysis comparisons, Sider's production retrospective on Haiku 4.5, and practitioner reports from Reddit/HN. Final map:

| Skill | Model | Why |
|-------|-------|-----|
| `/mn:health`, `/mn:sort`, `/mn:setup`, `/mn:save` | haiku | Rule-based routing, schema-constrained output, no synthesis |
| `/mn:connect`, `/mn:ask`, `/mn:session` | sonnet | Multi-source synthesis or semantic ranking with explanations |
| `/mn:review` | opus | Long JSONL + skill-gap reasoning; 1M context needed |

**`/mn:health` Step 5 is 1800x faster.** Previously looped `obsidian read` per note to find missing `## Связи` sections — ~180s on a 1000-note vault. Now one filesystem-level `grep -rL` against the vault path — **~49ms measured on a 999-note vault.** No more "skip on large vaults" caveat.

Typical wins on a warm instance:

| Command | v0.5.10 | v0.6.1 |
|---------|---------|--------|
| `/mn:health` | ~8s | ~1s (with Step 5 fix) |
| `/mn:ask` | ~6s | ~2s |
| `/mn:connect` | ~7s | ~2.5s |
| `/mn:save` | ~5s | ~1.5s (Haiku) |
| `/mn:review` rerun | ~10s | ~3s (cached scan) |

**`/mn:review` internals cleaned up.** The two inline Python heredocs (session JSONL scan + skill auto-discovery) now live in `plugins/mnemo/scripts/` with 60s/300s `/tmp` caches — repeated reviews in the same session are effectively instant.

Plus: parallel CLI calls documented in `/mn:ask`, `/mn:session`, `/mn:connect`. `context: fork` removed from index-only skills (warm-cache reuse).

### What's New in v0.5

**`/mn:review`** is your **end-of-session orchestrator**. Just run it and it handles everything:
- **Auto-saves** unsaved decisions and findings to Obsidian + claude-mem + memory/
- **Auto-creates** session notes with handoff for the next session
- Parses your session's JSONL file to know exactly which tools and skills were used
- Auto-discovers 200+ installed skills across all your plugins
- Classifies your session type (implementation, research, debugging...)
- Recommends remaining skills (commit, connect, health) — you pick which to run

**One command to end any session: `/mn:review`**

## Architecture

```
┌──────────────┐     ┌───────────────┐     ┌───────────────┐
│ Codex/Claude │────▶│ commands/     │────▶│    skills      │
│ coding agent │     │ skill invoke  │     │  memory-routing │
│              │     │ /mn or $skill │     │  session-review │
└──────────────┘     └───────────────┘     └───────────────┘
                            │                      │
                            │                ┌─────▼─────┐
                            │                │ Obsidian   │
                            │                │ CLI        │
                            │                └───────────┘
                      ~/.mnemo/config.json
```

**Commands** are thin wrappers for Claude Code that route to **skills** via the Skill tool. Codex invokes the same skills directly with `$skill-name` or implicit skill selection. This keeps the skill body shared while each host gets its native UX.

**Key design decisions:**
- **CLI-first** — uses `obsidian` CLI commands, not MCP ([70,000x cheaper](https://x.com/kepano))
- **Config-driven** — vault name, taxonomy, rules in `config.json`
- **Non-destructive** — skills report and suggest, never auto-delete or overwrite
- **Any taxonomy** — works with Zettelkasten, PARA, Atom/Molecule, or your own system

## Quick Start

### Install: Claude Code

```bash
# Add marketplace (one time)
claude plugin marketplace add jojoprison/mnemo

# Install plugin
claude plugin install mnemo@mnemo
```

Legacy installs through `jojoprison/claude-mnemo` continue to work through the GitHub repository redirect, but new installs should use `jojoprison/mnemo`.

### Install: Codex

```bash
codex plugin marketplace add jojoprison/mnemo
codex plugin install mnemo@mnemo
```

Codex discovers the shared skills from `plugins/mnemo/skills/`. Use `$mnemo:vault-search`, `$mnemo:memory-routing`, or let Codex invoke the relevant skill from its description.

### First Run

```
/mn:health
> What's your Obsidian vault name? main
> Saved to config.json. Running health check...
```

## Usage Examples

### Weekly vault checkup

```
/mn:health
```

```
📊 Vault Health Report (2026-04-07)

Total: 487 notes
  Atoms: 89 | Molecules: 23 | Sources: 34
  Sessions: 67 | MOCs: 14 | Inbox: 4

🔴 Orphans: 3
📬 Inbox backlog: 4 notes
🏆 Top-5 Hubs: MOC — Security (34), MOC — AI ML Tools (28)...
```

### Search your knowledge base

```
/mn:ask "what did we decide about pricing strategy?"
```

Returns synthesized answers with citations to specific notes.

### Discover hidden links

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

Finds notes related by concepts, tags, or entities — then asks before applying.

### Save decisions and findings

```
/mn:save "We chose PostgreSQL over DynamoDB for the audit log — better JSON querying"
```

Routes to Obsidian (Atom note) + claude-mem (semantic search) + memory/ (Claude's future context). If any backend is down, the others still work.

### End-of-session orchestrator (the only command you need)

```
/mn:review
```

Analyzes your session, **auto-saves** decisions, **auto-creates** session notes. Then asks about remaining skills (commit, connect, health).

### Session notes + handoff

```
/mn:session
```

Creates a session summary in Obsidian, updates the handoff file for the next session. No more "what was I doing yesterday?"

## Configuration

Run `/mn:setup` or copy manually:

```bash
mkdir -p ~/.mnemo
cp config.example.json ~/.mnemo/config.json
```

```json
{
  "vault": "main",
  "taxonomy": {
    "atom": { "prefix": "Atom — ", "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source": { "prefix": "Source — ", "tag": "source" },
    "session": { "prefix": "Session — ", "tag": "session" },
    "moc": { "prefix": "MOC — ", "tag": "moc" },
    "inbox": { "prefix": "Inbox — ", "tag": "inbox" }
  },
  "links_section": "## Links",
  "handoff_note": "Meta — Session Handoff",
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false },
    "memory_dir": { "enabled": true }
  }
}
```

All fields are optional. Skills ask on first use.

### Custom Taxonomy

mnemo doesn't force a note structure. Change `taxonomy` to match yours:

```json
{
  "taxonomy": {
    "permanent": { "prefix": "", "tag": "permanent" },
    "fleeting": { "prefix": "F: ", "tag": "fleeting" },
    "literature": { "prefix": "L: ", "tag": "literature" }
  }
}
```

## Cross-Session Continuity

The killer feature. When a session ends, `/mn:session` writes a handoff note:

```markdown
## Pending
- [ ] Check orphans after mass note creation
- [ ] Update MOC — AI Research with 3 new notes

## Context
- Researched WeChat agent ecosystem, all saved in Session — 2026-03-23
```

Next session reads this and picks up where you left off.

## Requirements

- [Claude Code](https://claude.ai/code) (Pro/Max/Team or API key)
- [Obsidian](https://obsidian.md) (free) — **must be running**
- [Obsidian CLI](https://github.com/kepano/obsidian-cli) — `obsidian` command in PATH

## Project Structure

```
mnemo/
├── plugins/mnemo/
│   ├── .claude-plugin/plugin.json
│   ├── .codex-plugin/plugin.json
│   ├── commands/mn/                 # User-facing /mn:* commands (thin routers)
│   │   ├── save.md                  # /mn:save      → mnemo:memory-routing
│   │   ├── session.md               # /mn:session   → mnemo:session-notes
│   │   ├── review.md                # /mn:review    → mnemo:session-review
│   │   ├── ask.md                   # /mn:ask       → mnemo:vault-search
│   │   ├── health.md                # /mn:health    → mnemo:vault-health
│   │   ├── connect.md               # /mn:connect   → mnemo:link-discovery
│   │   ├── sort.md                  # /mn:sort      → mnemo:inbox-triage
│   │   └── setup.md                 # /mn:setup     → mnemo:initial-setup
│   ├── skills/                      # Skill implementations (8)
│   │   ├── memory-routing/SKILL.md
│   │   ├── session-notes/SKILL.md
│   │   ├── session-review/SKILL.md
│   │   ├── vault-search/SKILL.md
│   │   ├── vault-health/SKILL.md
│   │   ├── link-discovery/SKILL.md
│   │   ├── inbox-triage/SKILL.md
│   │   └── initial-setup/SKILL.md
│   ├── references/                  # Shared docs (progressive disclosure)
│   │   ├── gotchas.md               # Common failures (IPC, stale cache, shell injection)
│   │   ├── config-schema.md         # Full ~/.mnemo/config.json reference
│   │   ├── tool-routing.md          # MCP-first hybrid rule + rationale
│   │   ├── triggers-implementation.md
│   │   ├── triggers-research.md
│   │   ├── triggers-debugging.md
│   │   └── triggers-universal.md
│   ├── assets/                      # Reusable templates
│   │   └── session-template.md
│   ├── scripts/                     # Shell & Python helpers
│   │   ├── session-scan.py          # JSONL parser with incremental read cache
│   │   ├── skills-discover.py       # Auto-discovery across Claude/Codex skill paths
│   │   ├── get-vault-path.sh        # obsidian vault → filesystem path
│   │   └── check-cm-version.sh      # claude-mem cache inspector
│   └── hooks/                       # Harness hooks
│       ├── hooks.json               # SessionStart async prewarm
│       └── prewarm.sh               # Warms /mn:review caches non-blocking
├── .github/workflows/
│   └── skill-lint.yml               # CI: validates SKILL.md frontmatter + refs
├── .agents/plugins/
│   └── marketplace.json             # Codex marketplace entry
├── scripts/
│   └── lint-skills.py               # Linter used by CI and locally
├── config.example.json
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## Inspired By

- [My-Brain-Is-Full-Crew](https://github.com/gnekt/My-Brain-Is-Full-Crew) — 8 AI agents managing Obsidian. Great concept, different approach: PARA-based, heavier. mnemo takes the best ideas and packages them as lightweight skills for **any** vault.
- [kepano/obsidian-cli](https://github.com/kepano/obsidian-cli) + [obsidian-skills](https://github.com/kepano/obsidian-skills) — CLI-first philosophy and the 70,000x token savings insight.
- [Zettelkasten](https://zettelkasten.de/), [Atomic/Molecular Notes](https://reasonabledeviations.com/2022/04/18/molecular-notes-part-1/), [Maps of Content](https://www.dsebastien.net/2022-05-15-maps-of-content/) — note taxonomy research.

## Contributing

PRs welcome. If you have a better prompt pattern, a new skill idea, or a taxonomy adapter — open a PR.

---

# Русский

## Что делает

**mnemo** дает Claude Code постоянную память через Obsidian vault. Восемь скиллов, которые берут на себя рутину управления знаниями.

Большинство инструментов «второго мозга» предполагают, что у тебя есть время все организовать. mnemo предполагает, что нет.

```
Ты работаешь → mnemo запоминает → Vault растет → Ты находишь потом
```

### Скиллы

| Скилл | Команда | Что делает |
|-------|---------|-----------|
| **health** | `/mn:health` | Аудит vault: orphans, битые ссылки, пропущенные секции, стагнирующие заметки |
| **ask** | `/mn:ask` | Поиск по vault и синтез ответа из нескольких заметок с цитатами |
| **connect** | `/mn:connect` | Находит скрытые связи между заметками |
| **sort** | `/mn:sort` | Классификация inbox-заметок в типы (atom, molecule, source...) |
| **session** | `/mn:session` | Сессионная заметка + cross-session handoff |
| **save** | `/mn:save` | Каскадное сохранение — Obsidian + claude-mem + memory/ |
| **review** | `/mn:review` | Оркестратор конца сессии — автосохраняет решения, создает session notes, рекомендует оставшиеся скиллы |
| **setup** | `/mn:setup` | Интерактивный онбординг |

### Почему не обычные плагины Obsidian?

Плагины Obsidian работают внутри Obsidian. mnemo работает внутри **Claude Code** — у него есть доступ ко всему контексту разработки, истории разговора и кодовой базе. Когда ты заканчиваешь 3-часовую сессию, `/mn:session` знает что ты делал, потому что был рядом.

### Что нового в v0.7.3

**Гибридный fork/inherit роутинг — больше нет 429 `Extra usage required for 1M context`.** tiered `model:` из v0.6.0 триггерил переключение модели на каждый вызов skill, что **заново вычитывает разговор без кеша**. На Max-подписке (где Opus авто-апгрейдится до 1M контекста) большой разговор + switch упирался в server-side 1M billing gate и падал с `API Error: Extra usage is required for 1M context`.

**Решение** разделяет скиллы по тому, нужен ли им контекст сессии:

- **4 скилла в форке** (`context: fork` + конкретная модель) — `/mn:health`, `/mn:connect`, `/mn:sort`, `/mn:setup`. Изолированные subagent'ы со своим 200K контекстом, главная сессия не тронута.
- **4 скилла с inherit** (`model: inherit`) — `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review`. Используют модель, которую ты выбрал через `/model` — ты контролируешь.

`/mn:review` получил подсказку: *"перед review запусти `/model opus[1m]` для максимальной глубины"*. Сохраняет дефолтную экономию без потери потолка качества. Linter расширен — принимает `model: inherit` и `context: fork`, отклоняет противоречащую комбинацию `fork + inherit`.

### Что нового в v0.7.2

**CI lint для SKILL.md.** `scripts/lint-skills.py` проверяет frontmatter, whitelist моделей, лимит строк, и каждый путь на `references/` / `scripts/` / `assets/` который упомянут в скилле. Запускается на каждом push через `.github/workflows/skill-lint.yml`. Ловит битые ссылки после переименований, устаревшие указатели на скрипты, случайный `model: opus-42`, переросшие скиллы. Локально: `python3 scripts/lint-skills.py`.

**`/mn:session` реально грузит шаблон.** Step 3 теперь явно делает `cat` на `assets/session-template.md` перед заполнением плейсхолдеров — раньше шаблон упоминался, но не читался.

**`/mn:review` всегда грузит triggers.** Step 4 теперь явно делает `cat` на `triggers-{type}.md` + `triggers-universal.md` + project-local `skill-triggers.md` (если есть). Больше не полагается на то, что Claude вспомнит сам.

**README "Project Structure" актуален** — добавлены `references/`, `assets/`, `hooks/`, `scripts/`, CI workflow.

### Что нового в v0.7.1

**Polish-релиз после skill-creator аудита.** Убрали ~100 строк дублированных gotcha/config/tool-routing блоков из 7 SKILL.md — вынесли в `plugins/mnemo/references/`. Skills теперь подгружают ref только когда нужно (progressive disclosure). `session-review` ужали с 262 → 222 строк, разбив огромную trigger matrix на файлы по типу сессии.

**Более pushy descriptions** чтоб Claude не «забывал» вызывать skills (реальная проблема, на которую указал skill-creator). 7 skills получили русские триггер-фразы и proactive формулировки «use whenever».

**Incremental session scan.** `session-scan.py` теперь читает только дозаписанные байты JSONL. Первый `/mn:review` на сессии 5000+ строк: ~200ms → ~20ms парсинга.

**`/mn:sort` bulk mode.** Скажи «применить все» — и пропустит пер-note подтверждения.

**`/mn:setup` идемпотентный handoff.** Повторный запуск setup больше не перезаписывает существующий handoff.

### Что нового в v0.7.0

**Интеграция с claude-mem v12.3.9.** Если параллельно запущен [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem), mnemo теперь умеет с ним дружить:

- **`/mn:health` Step 0** показывает предупреждения про stale cache + major-version skew — реальный failure mode, где Stop hooks указывают на удалённый `CLAUDE_PLUGIN_ROOT` после `/plugin update`.
- **`/mn:save` Step 2** автоматически детектит `claude_mem_version` и тегирует каждое observation линками `obsidian_note` + `obsidian_vault`. Фундамент для будущего режима `/mn:ask --deep` который покажет semantic-search hits рядом с полными заметками vault'а.

### Что нового в v0.6.2

**`/mn:connect` делает один grep вместо N `obsidian search` вызовов.** Одно прохождение по filesystem для всех концептов, объединённых OR в regex. **7 концептов: 1.26с → 50ms (25x).**

**`/mn:health` Steps 1-4 параллельно.** Orphans, unresolved, tags, files-count — независимые CLI queries — задокументированы как parallel batches. 720ms → 180ms.

**SessionStart prewarm hook.** Кеши `/mn:review` прогреваются асинхронно на старте сессии — **первый** review мгновенный вместо ~10с.

### Что нового в v0.6.1

**Модели перевыставлены по реальным бенчмаркам.** В v0.6.0 тиринг был интуитивным. Перед v0.6.1 прошерстил Anthropic docs, Artificial Analysis сравнения, production-ретро от Sider по Haiku 4.5, обсуждения на Reddit/HN. Итоговая карта:

| Скилл | Модель | Почему |
|-------|--------|--------|
| `/mn:health`, `/mn:sort`, `/mn:setup`, `/mn:save` | haiku | Rule-based routing, schema-constrained вывод, без синтеза |
| `/mn:connect`, `/mn:ask`, `/mn:session` | sonnet | Multi-source synthesis или семантическое ранжирование с объяснением |
| `/mn:review` | opus | Длинный JSONL + skill-gap reasoning; нужен 1M контекст |

**`/mn:health` Step 5 стал в 1800 раз быстрее.** Раньше в цикле `obsidian read` по каждой заметке для проверки `## Связи` — ~180с на vault из 1000 заметок. Теперь один recursive `grep -rL` по filesystem-пути vault'а — **~49ms на 999-заметочном vault'е.** Больше никаких "skip на больших vault'ах".

Типичный выигрыш на прогретом инстансе:

| Команда | v0.5.10 | v0.6.1 |
|---------|---------|--------|
| `/mn:health` | ~8с | ~1с (с фиксом Step 5) |
| `/mn:ask` | ~6с | ~2с |
| `/mn:connect` | ~7с | ~2.5с |
| `/mn:save` | ~5с | ~1.5с (Haiku) |
| `/mn:review` повтор | ~10с | ~3с (кеш) |

**Внутренности `/mn:review` почистили.** Два inline-Python heredoc (скан JSONL + автодискавери скиллов) переехали в `plugins/mnemo/scripts/` с кешем 60с/300с в `/tmp` — повторные ревью в одной сессии почти мгновенны.

Плюс: parallel CLI-вызовы задокументированы в `/mn:ask`, `/mn:session`, `/mn:connect`. `context: fork` убран с index-only скиллов (warm-cache reuse).

### Что нового в v0.5

**`/mn:review`** — **оркестратор конца сессии**. Одна команда — и всё:
- **Автосохранение** решений и находок в Obsidian + claude-mem + memory/
- **Автосоздание** session notes с handoff для следующей сессии
- Парсит JSONL — знает какие инструменты и скиллы были вызваны
- Автообнаружение 200+ скиллов по всем плагинам
- Определяет тип сессии (implementation, research, debugging...)
- Рекомендует оставшееся (commit, connect, health) — ты выбираешь

**Одна команда для завершения сессии: `/mn:review`**

## Установка

### Claude Code

```bash
# Добавить marketplace (один раз)
claude plugin marketplace add jojoprison/mnemo

# Установить плагин
claude plugin install mnemo@mnemo
```

Старый путь `jojoprison/claude-mnemo` остаётся совместимым через GitHub redirect, но новые установки должны использовать `jojoprison/mnemo`.

### Codex

```bash
codex plugin marketplace add jojoprison/mnemo
codex plugin install mnemo@mnemo
```

В Codex вызывай skills напрямую (`$mnemo:vault-search`, `$mnemo:memory-routing`) или полагайся на auto-invocation по описанию.

### Первый запуск

```
/mn:health
> Как называется твой Obsidian vault? main
> Сохранено. Запускаю проверку...
```

## Примеры

### Аудит vault

```
/mn:health
```

```
📊 Здоровье Vault (2026-04-07)

Всего: 487 заметок
  Atoms: 89 | Molecules: 23 | Sources: 34

🔴 Orphans: 3
📬 Inbox: 4 заметки
🏆 Топ-5 хабов: MOC — Security (34), MOC — AI ML Tools (28)...
```

### Поиск по знаниям

```
/mn:ask "что мы решили по ценообразованию?"
```

Синтезирует ответ из нескольких заметок с цитатами и ссылками.

### Скрытые связи

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

Находит связи по концептам, тегам, сущностям. Спрашивает перед применением.

### Сохранение решений

```
/mn:save "Выбрали PostgreSQL вместо DynamoDB для audit log — лучше JSON querying"
```

Роутит в Obsidian (Atom) + claude-mem (семантический поиск) + memory/ (контекст для Claude). Если backend упал — остальные работают.

### Ревью сессии (единственная команда на конец)

```
/mn:review
```

Анализирует сессию, **автоматически** сохраняет решения и создает session notes. Потом спрашивает про остальное (commit, connect, health).

### Сессионные заметки

```
/mn:session
```

Создает заметку в Obsidian, обновляет handoff для следующей сессии.

## Конфигурация

`/mn:setup` или вручную:

```bash
mkdir -p ~/.mnemo
cp config.example.json ~/.mnemo/config.json
```

Все поля опциональны. Скиллы спросят при первом запуске.

## Cross-Session Continuity

Киллер-фича. `/mn:session` записывает handoff-заметку. Следующая сессия подхватывает с того места. Больше никакого «а что я вчера делал?»

## Требования

- [Claude Code](https://claude.ai/code) (Pro/Max/Team или API ключ)
- [Obsidian](https://obsidian.md) (бесплатно) — **должен быть запущен**
- [Obsidian CLI](https://github.com/kepano/obsidian-cli) — `obsidian` в PATH

---

# 中文

## 功能介绍

**mnemo** 为 Claude Code 提供基于 Obsidian 的持久记忆层。八个技能自动处理知识管理的繁琐工作，让你专注于思考。

大多数「第二大脑」工具假设你有时间整理。mnemo 假设你没有。

```
你工作 → mnemo 记住 → Vault 成长 → 你以后能找到
```

### 技能列表

| 技能 | 命令 | 功能 |
|------|------|------|
| **health** | `/mn:health` | Vault 审计：孤立笔记、断链、缺失章节、陈旧笔记、增长统计 |
| **ask** | `/mn:ask` | 搜索 vault 并从多个笔记中综合答案，附带引用 |
| **connect** | `/mn:connect` | 发现笔记之间隐藏的联系 |
| **sort** | `/mn:sort` | 将收件箱笔记分类为正确类型（atom、molecule、source...） |
| **session** | `/mn:session` | 自动生成会话摘要 + 跨会话上下文传递 |
| **save** | `/mn:save` | 级联保存 — Obsidian + claude-mem + memory/，优雅降级 |
| **review** | `/mn:review` | 会话结束编排器 — 自动保存决策、创建会话笔记、推荐其余技能 |
| **setup** | `/mn:setup` | 交互式引导配置 |

### 为什么不用 Obsidian 插件？

Obsidian 插件在 Obsidian 内部运行。mnemo 在 **Claude Code** 内部运行——它可以访问你的整个开发上下文、对话历史和代码库。当你结束一个 3 小时的调试会话时，`/mn:session` 知道你做了什么，因为它全程在场。

### v0.7.3 新特性

**混合 fork/inherit 路由 — 消除 `Extra usage required for 1M context` 429 错误。** v0.6.0 的分层 `model:` 覆盖在每次技能调用时强制切换模型，导致**无缓存重新读取整个会话**。在 Max 套餐上（Opus 自动升级到 1M 上下文），大会话 + 切换会触发 Anthropic 服务端 1M 计费门控，返回 `API Error: Extra usage is required for 1M context`。

**修复方案**按是否需要会话上下文拆分技能：

- **4 个技能使用 fork**（`context: fork` + 具体模型）—— `/mn:health`、`/mn:connect`、`/mn:sort`、`/mn:setup`。在隔离 subagent 中运行，独立 200K 上下文，主会话零影响。
- **4 个技能使用 inherit**（`model: inherit`）—— `/mn:ask`、`/mn:save`、`/mn:session`、`/mn:review`。使用你通过 `/model` 选择的模型——你掌控一切。

`/mn:review` 新增提示：*"运行 review 前先执行 `/model opus[1m]` 以获得最深度分析。"* 保留默认节省同时不丢失之前强制 opus 的质量上限。Linter 扩展支持 `model: inherit` 和 `context: fork`，并拒绝相互矛盾的 `fork + inherit` 组合。

### v0.7.2 新特性

**SKILL.md CI lint。** `scripts/lint-skills.py` 校验 frontmatter、模型白名单、行数上限，以及技能中提到的每个 `references/` / `scripts/` / `assets/` 路径是否存在。通过 `.github/workflows/skill-lint.yml` 在每次 push 时运行。捕获重命名后的失效引用、过期脚本指针、`model: opus-42` 之类的错误、超大技能文件。本地运行：`python3 scripts/lint-skills.py`。

**`/mn:session` 真正加载模板。** Step 3 现在会显式 `cat` 读取 `assets/session-template.md` 然后填充占位符——之前模板仅被提及，从未真正加载。

**`/mn:review` 始终加载 triggers。** Step 4 现在显式 `cat` 读取 `triggers-{type}.md` + `triggers-universal.md` + 项目本地 `skill-triggers.md`（如存在）。不再依赖 Claude 自己去记得读取。

**README "Project Structure" 对齐实际状态** — 补充 `references/`、`assets/`、`hooks/`、`scripts/`、CI workflow。

### v0.7.1 新特性

**skill-creator 审计驱动的 polish 版本。** 从 7 个 SKILL.md 中移除 ~100 行重复的 gotchas/config/tool-routing 描述，提取到 `plugins/mnemo/references/`。技能现在仅在需要时加载引用（progressive disclosure）。仅 `session-review` 就从 262 → 222 行，将庞大的 trigger matrix 拆分为按会话类型的文件。

**更积极的 descriptions** 防止 Claude 欠触发技能（skill-creator 指出的真实问题）。7 个 skill 加入俄语触发短语和主动式 "use whenever" 表述。

**增量会话扫描。** `session-scan.py` 现在只读取自上次扫描以来追加的 JSONL 字节。5000 行会话的首次 `/mn:review`：~200ms → ~20ms 解析时间。

**`/mn:sort` 批量模式。** 说 "accept all" 即可跳过逐条确认。

**`/mn:setup` 幂等 handoff。** 重新运行 setup 不再覆盖已有的 handoff 笔记。

### v0.7.0 新特性

**claude-mem v12.3.9 集成。** 如果你也安装了 [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)，mnemo 现在会与它协作：

- **`/mn:health` Step 0** 显示过期缓存 + 主版本偏移警告——真实的故障模式：`/plugin update` 后 Stop hooks 指向已删除的 `CLAUDE_PLUGIN_ROOT`。
- **`/mn:save` Step 2** 自动检测 `claude_mem_version`，并为每个 observation 标记 `obsidian_note` + `obsidian_vault` 反向链接。为未来的 `/mn:ask --deep` 模式打基础——它将在 semantic-search 结果旁显示完整 vault 笔记。

### v0.6.2 新特性

**`/mn:connect` 用一个 grep 替代 N 次 `obsidian search` 调用。** 单次文件系统扫描处理所有合并为 OR 正则的概念。**7 个概念：1.26 秒 → 50ms（25 倍）。**

**`/mn:health` Steps 1-4 并行运行。** Orphans、unresolved、tags、files-count 是独立的 CLI 查询——记录为并行批次。720ms → 180ms。

**SessionStart 预热 hook。** `/mn:review` 的缓存在会话启动时异步预热——**第一次** 审查瞬时完成，而不是约 10 秒。

### v0.6.1 新特性

**基于真实基准校准的模型分层。** v0.6.0 的分层凭直觉。v0.6.1 重新平衡，参考了 Anthropic 文档、Artificial Analysis 对比、Sider 关于 Haiku 4.5 的生产总结，以及 Reddit/HN 的从业者报告。最终映射：

| 技能 | 模型 | 原因 |
|------|------|------|
| `/mn:health`, `/mn:sort`, `/mn:setup`, `/mn:save` | haiku | 基于规则的路由、模式约束输出、无综合 |
| `/mn:connect`, `/mn:ask`, `/mn:session` | sonnet | 多源综合或带解释的语义排序 |
| `/mn:review` | opus | 长 JSONL + 技能缺口推理；需要 1M 上下文 |

**`/mn:health` Step 5 快了 1800 倍。** 以前按笔记循环调用 `obsidian read` 查找缺失的 `## Связи`——1000 笔记的 vault 约 180 秒。现在单次 `grep -rL` 直接扫描 vault 文件系统路径——**999 笔记 vault 实测 ~49ms**。不再需要"大 vault 跳过此步"的警告。

预热实例下的典型提升：

| 命令 | v0.5.10 | v0.6.1 |
|------|---------|--------|
| `/mn:health` | ~8秒 | ~1秒 (Step 5 修复) |
| `/mn:ask` | ~6秒 | ~2秒 |
| `/mn:connect` | ~7秒 | ~2.5秒 |
| `/mn:save` | ~5秒 | ~1.5秒 (Haiku) |
| `/mn:review` 重跑 | ~10秒 | ~3秒 (缓存) |

**`/mn:review` 内部清理。** 两个内联 Python heredoc（JSONL 扫描 + 技能自动发现）移到 `plugins/mnemo/scripts/`，配合 `/tmp` 60 秒/300 秒缓存——同一会话内重复审查几乎瞬时完成。

另外：`/mn:ask`、`/mn:session`、`/mn:connect` 中记录了并行 CLI 调用。索引型技能移除了 `context: fork`（复用 warm cache）。

### v0.5 新特性

**`/mn:review`** 是**会话结束编排器**。一个命令搞定一切：
- **自动保存**未持久化的决策和发现到 Obsidian + claude-mem + memory/
- **自动创建**会话笔记和交接文件
- 解析 JSONL 文件，精确知道使用了哪些工具和技能
- 自动发现 200+ 已安装技能
- 识别会话类型（实现、研究、调试...）
- 推荐其余技能（commit、connect、health）——你选择运行哪些

**结束会话只需一个命令：`/mn:review`**

## 安装

### Claude Code

```bash
# 添加市场（一次性）
claude plugin marketplace add jojoprison/mnemo

# 安装插件
claude plugin install mnemo@mnemo
```

旧路径 `jojoprison/claude-mnemo` 仍可通过 GitHub redirect 工作；新安装请使用 `jojoprison/mnemo`。

### Codex

```bash
codex plugin marketplace add jojoprison/mnemo
codex plugin install mnemo@mnemo
```

Codex 可以直接调用 skills（如 `$mnemo:vault-search`、`$mnemo:memory-routing`），也可以按 description 自动触发。

### 首次运行

```
/mn:health
> 你的 Obsidian vault 名称是？ main
> 已保存。正在运行健康检查...
```

## 使用示例

### Vault 审计

```
/mn:health
```

```
📊 Vault 健康报告 (2026-04-07)

总计：487 个笔记
  Atoms: 89 | Molecules: 23 | Sources: 34

🔴 孤立笔记：3
📬 收件箱：4 个笔记待分类
🏆 前5大枢纽：MOC — Security (34), MOC — AI ML Tools (28)...
```

### 知识搜索

```
/mn:ask "我们对定价策略做了什么决定？"
```

从多个笔记中综合答案，附带引用和链接。

### 发现隐藏联系

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

通过概念、标签、实体找到关联。应用前会询问确认。

### 保存决策

```
/mn:save "选择了 PostgreSQL 而不是 DynamoDB 用于审计日志——JSON 查询更好"
```

路由到 Obsidian（Atom 笔记）+ claude-mem（语义搜索）+ memory/（Claude 的未来上下文）。任何后端宕机，其他仍然工作。

### 会话审查（会话结束只需这一个命令）

```
/mn:review
```

分析会话，**自动**保存决策并创建会话笔记。然后询问其余操作（commit、connect、health）。

### 会话笔记

```
/mn:session
```

在 Obsidian 中创建会话摘要，更新下次会话的交接文件。

## 配置

`/mn:setup` 或手动：

```bash
mkdir -p ~/.mnemo
cp config.example.json ~/.mnemo/config.json
```

所有字段可选。技能会在首次使用时询问。

## 跨会话连续性

杀手级功能。`/mn:session` 写入交接笔记，下次会话自动接续。再也不用问「我昨天在做什么？」

## 环境要求

- [Claude Code](https://claude.ai/code)（Pro/Max/Team 或 API 密钥）
- [Obsidian](https://obsidian.md)（免费）——**必须运行中**
- [Obsidian CLI](https://github.com/kepano/obsidian-cli)——`obsidian` 命令在 PATH 中

---

Made with care by [Claude Code](https://claude.ai) + [jojoprison](https://github.com/jojoprison)
