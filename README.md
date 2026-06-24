# mnemo

> Persistent memory layer for Codex and Claude Code — your Obsidian vault on autopilot.

[![Codex](https://img.shields.io/badge/Codex-skills-black?style=flat-square)](https://developers.openai.com/codex/skills)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-blueviolet?style=flat-square)](https://claude.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Skills](https://img.shields.io/badge/Skills-7-blue?style=flat-square)](plugins/mnemo/skills/)
[![Obsidian](https://img.shields.io/badge/Obsidian-compatible-7C3AED?style=flat-square&logo=obsidian&logoColor=white)](https://obsidian.md)

**[English](#what-it-does)** | **[Русский](#что-делает)** | **[中文](#功能介绍)**

---

## What It Does

**mnemo** gives Codex and Claude Code a persistent memory through your Obsidian vault. Seven skills handle the boring parts of knowledge management so you can focus on thinking.

Most "second brain" tools assume you have time to organize. mnemo assumes you don't.

```
You work → mnemo remembers → Your vault grows → You find things later
```

### The Skills

| Skill | Command | What it does |
|-------|---------|-------------|
| **save** | `/mn:save` | Routing cascade — sends a recall item to Obsidian (+ `memory/`, + claude-mem if enabled), or an actionable rule to `.claude/rules/` (path-scoped auto-inject), with graceful degradation |
| **session** | `/mn:session` | Session summary note + cross-session handoff for the next session |
| **review** | `/mn:review` | End-of-session orchestrator — audits the session, auto-runs save + session, recommends the rest |
| **ask** | `/mn:ask` | Search vault (+ Claude's `memory/` index), synthesize a cited answer, date each source by recency, and ground current-state answers in the project's git history |
| **connect** | `/mn:connect` | Discover hidden connections between notes — suggests, never auto-applies |
| **health** | `/mn:health` | Vault audit: orphans, broken links, type-aware review candidates (+ optional LLM lint), growth stats |
| **setup** | `/mn:setup` | Interactive onboarding — vault name, taxonomy, language |

### When to Use Which

| Moment | Command |
|--------|---------|
| The instant a fact/decision/finding appears, mid-session | `/mn:save` — save as you go, **don't batch** (compaction can drop context at any time) |
| Recall earlier context / past decisions | `/mn:ask` |
| Just created notes — surface hidden links | `/mn:connect` |
| End of work, **or before a long run risks context compaction** | `/mn:session` — writes the journey note + handoff |
| One command to close a session | `/mn:review` — audits + auto-runs save & session + recommends the rest |
| Periodically / after 3+ new notes | `/mn:health` |

`save` and `session` are complementary, not either/or: `save` pins discrete facts **as they happen**; `session` writes the narrative + handoff **at the end**. `review` orchestrates both — but its auto-run is gated by a significance judgment, so the loss-proof habit is `save` throughout **plus** an explicit `session`/`review` at the end.

### Why Not Just Use Obsidian Plugins?

Obsidian plugins run inside Obsidian. mnemo runs inside your coding agent — **Codex or Claude Code** — so it has access to your development context, conversation history, and codebase. When you finish a 3-hour debugging session, `/mn:session` knows what you did because it was there.

### What's New (v0.14.x)

- **Knowledge compounds + self-snoozing lint + research gaps** (v0.14.0) — three opt-in, on-philosophy distillations from a full audit of Karpathy's "LLM Wiki" pattern. `/mn:ask` can fold a real synthesis **back into the vault as a Molecule** (sources pre-linked) so explorations accumulate; `review.lint.autoStampReviewed` lets the lint stamp `reviewed:` on still-valid notes to close the snooze loop; `/mn:health` surfaces **research-gap candidates** (populous topic with no MOC, recurring external with no Source note). All opt-in: a default install writes nothing (the content lint is off), the compounding save is user-confirmed, and the lone auto-write — the `reviewed:` stamp — only fires once you turn the lint on.
- **Recall grounded in live code** (v0.13.0) — for "is this still true / what changed" questions inside a git project, `/mn:ask` cross-checks the repo's recent commits and flags any note a newer commit may have outdated. Optional code-knowledge-graph backend via `recall.codeGraph` (Graphify / Sourcegraph / ast-grep…), off by default.
- **Recency-aware recall** (v0.12.0) — `/mn:ask` now dates every source it cites (git last-commit when the vault is a repo, else file mtime + `reviewed`/`date` frontmatter) and flags an answer that rests on stale notes.
- **Type-aware review + content lint** (v0.11.0) — `/mn:health` flags stale notes by a per-**type** budget (`review.staleDays`) instead of a flat 30 days, with a `reviewed:` snooze and per-note `ttl:`; an opt-in LLM lint (`review.lint.enabled`) re-reads candidates for outdated/contradicting claims — Karpathy's "lint your wiki". Changelog moved to Keep a Changelog v2 + GitHub Releases.
- **Codex/Claude command parity** (v0.10.2–0.10.3) — full `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review` aliases on Codex; accidental `/mnemo:mn:*` now routes instead of failing.
- **Autodream-aware memory index** (v0.10.0–0.10.1) — `memory/MEMORY.md` is a *lean* index: one `| File | Read when… |` row per topic file, never a paragraph. Claude Code hard-truncates it at ~24.4 KB on load, so `/mn:health` warns past a configurable `memory.indexWarnKB` (default 22). `/mn:ask` now also recalls from the `memory/` index, not just the vault.
- **PKM-canon + leaner skill set** (v0.9.0) — removed `inbox-triage` (**8 → 7 skills**): in an agent-driven flow, typed notes are written directly, so there's nothing to triage. Baked in note-naming rules (`# . / .md` forbidden), hub notes for short names, and `metadataCache`-over-CLI-cache for accurate link checks.
- **Dual-runtime** (v0.8.0–0.8.2) — renamed `claude-mnemo` → `mnemo`; native Codex support alongside Claude Code from one shared skill set.

Full version-by-version history: [CHANGELOG.md](CHANGELOG.md).

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

**Commands** are thin wrappers for Claude Code that route to **skills** via the Skill tool. Codex invokes the same skills directly with `$skill-name` or implicit skill selection. The skill body is shared; each host gets its native UX.

**Key design decisions:**
- **CLI-first** — uses `obsidian` CLI for reads/search, not MCP ([70,000x cheaper](https://x.com/kepano)); MCP only for markdown writes (shell-safety)
- **Config-driven** — vault name, taxonomy, rules in `config.json`
- **Non-destructive** — skills report and suggest, never auto-delete or overwrite
- **Any taxonomy** — works with Zettelkasten, PARA, Atom/Molecule, or your own system

→ Full rationale and **non-goals** (features deliberately not shipped — auto-ingest, web-search imputation, `hot.md` — each with how to add it): [docs/design-decisions.md](docs/design-decisions.md).

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
codex plugin add mnemo@mnemo
```

Codex discovers the shared skills from `plugins/mnemo/skills/`. Use the short aliases `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review`, or let Codex invoke the relevant skill from its description. The longer skill names (`mnemo:vault-search`, `mnemo:memory-routing`, `mnemo:session-notes`, `mnemo:session-review`) remain available for compatibility. If you accidentally type `/mnemo:mn:*`, mnemo routes it too, but `/mn:*` is the canonical form.

### First Run

```
/mn:health
> What's your Obsidian vault name? main
> Saved to config.json. Running health check...
```

## Usage Examples

### Save decisions and findings (any time, as they happen)

```
/mn:save "We chose PostgreSQL over DynamoDB for the audit log — better JSON querying"
```

Routes a recall item to Obsidian (an Atom note) + `memory/` (Claude's future context) + claude-mem (semantic search, if enabled); routes an actionable rule ("never X / always Y" tied to code) to `.claude/rules/<domain>.md` (path-scoped auto-inject) instead. If any backend is down, the others still work.

### End-of-session orchestrator (the one command to close a session)

```
/mn:review
```

Analyzes your session, **auto-saves** decisions, **auto-creates** session notes, then asks about remaining skills (commit, connect, health).

### Session notes + handoff

```
/mn:session
```

Creates a session summary in Obsidian and updates the handoff file for the next session. No more "what was I doing yesterday?"

### Search your knowledge base

```
/mn:ask "what did we decide about pricing strategy?"
```

Synthesized answers with citations to specific notes — across the vault and Claude's `memory/` index.

### Discover hidden links

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

Finds notes related by concepts, tags, or entities — then asks before applying.

### Weekly vault checkup

```
/mn:health
```

```
📊 Vault Health Report (2026-04-07)

Total: 487 notes
  Atoms: 89 | Molecules: 23 | Sources: 34
  Sessions: 67 | MOCs: 14

🔴 Orphans: 3
🏆 Top-5 Hubs: MOC — Security (34), MOC — AI ML Tools (28)...
```

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
    "moc": { "prefix": "MOC — ", "tag": "moc" }
  },
  "links_section": "## Links",
  "handoff_note": "Meta — Session Handoff",
  "memory": { "indexWarnKB": 22 },
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false },
    "memory_dir": { "enabled": true },
    "project_rules": { "enabled": true },
    "claude_md": { "enabled": false }
  },
  "review": {
    "staleDays": { "default": 30, "atom": 60, "molecule": 120, "source": 180, "session": 90, "moc": 365 },
    "lint": { "enabled": false, "maxCandidates": 15, "model": "haiku", "autoStampReviewed": true }
  },
  "recall": { "codeGraph": null }
}
```

All fields are optional. Skills ask on first use. `review.*` tunes `/mn:health` staleness per note type plus the optional content lint — see [config-schema.md](plugins/mnemo/references/config-schema.md).

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

The next session reads this and picks up where you left off.

## Requirements

- [Claude Code](https://claude.ai/code) (Pro/Max/Team or API key) **or** [Codex](https://developers.openai.com/codex/skills)
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
│   │   └── setup.md                 # /mn:setup     → mnemo:initial-setup
│   ├── skills/                      # Skill implementations (7)
│   │   ├── memory-routing/SKILL.md
│   │   ├── session-notes/SKILL.md
│   │   ├── session-review/SKILL.md
│   │   ├── vault-search/SKILL.md
│   │   ├── vault-health/SKILL.md
│   │   ├── link-discovery/SKILL.md
│   │   └── initial-setup/SKILL.md
│   ├── references/                  # Shared docs (progressive disclosure)
│   │   ├── gotchas.md               # Common failures (IPC, stale cache, shell injection)
│   │   ├── config-schema.md         # Full ~/.mnemo/config.json reference
│   │   ├── tool-routing.md          # MCP-for-writes / CLI-for-reads rule + rationale
│   │   ├── triggers-implementation.md
│   │   ├── triggers-research.md
│   │   ├── triggers-debugging.md
│   │   └── triggers-universal.md
│   ├── assets/                      # Reusable templates
│   │   └── session-template.md
│   ├── scripts/                     # Shell & Python helpers
│   │   ├── session-scan.py          # JSONL parser (Claude + Codex) with incremental cache
│   │   ├── skills-discover.py       # Auto-discovery across Claude/Codex skill paths
│   │   ├── get-vault-path.sh        # obsidian vault → filesystem path
│   │   ├── review-candidates.py     # type-aware staleness scan for /mn:health
│   │   └── check-cm-version.sh      # claude-mem cache inspector
│   └── hooks/                       # Harness hooks
│       ├── hooks.json               # SessionStart async prewarm
│       └── prewarm.sh               # Warms /mn:review caches non-blocking
├── .claude-plugin/marketplace.json  # Claude Code marketplace entry
├── .agents/plugins/marketplace.json # Codex marketplace entry
├── .github/workflows/skill-lint.yml # CI: validates SKILL.md frontmatter + refs
├── .github/workflows/release.yml    # CI: mirror CHANGELOG section → GitHub Release on tag
├── scripts/lint-skills.py           # Linter used by CI and locally
├── docs/codex.md                    # Codex install, invocation, runtime differences
├── AGENTS.md · CONTRIBUTING.md · CHANGELOG.md · TESTING.md · LICENSE
```

## Inspired By

- [My-Brain-Is-Full-Crew](https://github.com/gnekt/My-Brain-Is-Full-Crew) — 8 AI agents managing Obsidian. Great concept, different approach: PARA-based, heavier. mnemo takes the best ideas and packages them as lightweight skills for **any** vault.
- [kepano/obsidian-cli](https://github.com/kepano/obsidian-cli) + [obsidian-skills](https://github.com/kepano/obsidian-skills) — CLI-first philosophy and the 70,000x token savings insight.
- [Zettelkasten](https://zettelkasten.de/), [Atomic/Molecular Notes](https://reasonabledeviations.com/2022/04/18/molecular-notes-part-1/), [Maps of Content](https://www.dsebastien.net/2022-05-15-maps-of-content/) — note taxonomy research.
- [Andrej Karpathy's "LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (2026) — the operational model mnemo implements: an AI reads sources once, builds & maintains an interlinked markdown wiki, then "lints" it. `/mn:health` is that lint.

## Contributing

PRs welcome. If you have a better prompt pattern, a new skill idea, or a taxonomy adapter — open a PR.

---

# Русский

## Что делает

**mnemo** даёт Codex и Claude Code постоянную память через Obsidian vault. Семь скиллов берут на себя рутину управления знаниями, чтобы ты думал, а не сортировал.

Большинство инструментов «второго мозга» предполагают, что у тебя есть время всё организовать. mnemo предполагает, что нет.

```
Ты работаешь → mnemo запоминает → Vault растёт → Ты находишь потом
```

### Скиллы

| Скилл | Команда | Что делает |
|-------|---------|-----------|
| **save** | `/mn:save` | Каскад роутинга — отправляет один факт/решение/находку в Obsidian (+ `memory/`, + claude-mem если включён), с graceful degradation |
| **session** | `/mn:session` | Сессионная заметка + cross-session handoff для следующей сессии |
| **review** | `/mn:review` | Оркестратор конца сессии — аудит сессии, авто-запуск save + session, рекомендация остального |
| **ask** | `/mn:ask` | Поиск по vault (+ индекс `memory/` для Claude), синтез ответа с цитатами, датировка источников по свежести + заземление ответов про текущее состояние в git-истории проекта |
| **connect** | `/mn:connect` | Находит скрытые связи между заметками — предлагает, не применяет сам |
| **health** | `/mn:health` | Аудит vault: orphans, битые ссылки, type-aware кандидаты на ревью (+ опц. LLM-линт), статистика роста |
| **setup** | `/mn:setup` | Интерактивный онбординг — имя vault, таксономия, язык |

### Когда что использовать

| Момент | Команда |
|--------|---------|
| Как только появился факт/решение/находка, по ходу сессии | `/mn:save` — фиксируй сразу, **не копи** (компакт может срезать контекст в любой момент) |
| Вспомнить контекст / прошлые решения | `/mn:ask` |
| Только что создал заметки — найти скрытые связи | `/mn:connect` |
| Конец работы, **или перед длинным прогоном, рискующим компактом** | `/mn:session` — журнал сессии + handoff |
| Одна команда на закрытие сессии | `/mn:review` — аудит + авто-запуск save & session + рекомендации |
| Периодически / после 3+ новых заметок | `/mn:health` |

`save` и `session` дополняют друг друга, это не «или-или»: `save` фиксирует дискретные факты **по ходу**; `session` пишет нарратив + handoff **в конце**. `review` оркестрирует оба — но его авто-запуск гейтится оценкой значимости, поэтому защищённая от потерь привычка = `save` по ходу **плюс** явный `session`/`review` в конце.

### Почему не обычные плагины Obsidian?

Плагины Obsidian работают внутри Obsidian. mnemo работает внутри твоего кодинг-агента — **Codex или Claude Code** — у него есть доступ ко всему контексту разработки, истории разговора и кодовой базе. Когда ты заканчиваешь 3-часовую сессию, `/mn:session` знает что ты делал, потому что был рядом.

### Что нового (v0.14.x)

- **Знание накапливается + самоснузящийся линт + research-гэпы** (v0.14.0) — три opt-in, на-философии вывода из полного аудита паттерна Карпати «LLM Wiki». `/mn:ask` может свернуть настоящий синтез **обратно в vault как Molecule** (источники уже слинкованы), чтобы исследования накапливались; `review.lint.autoStampReviewed` позволяет линту штамповать `reviewed:` на still-valid заметках, замыкая петлю снуза; `/mn:health` показывает **research-gap кандидатов** (популярный топик без MOC, частый внешний источник без Source-заметки). Всё opt-in: дефолтная установка ничего не пишет (контент-линт выключен), сохранение синтеза — по подтверждению, а единственная авто-запись (штамп `reviewed:`) срабатывает только когда ты включишь линт.
- **Recall, заземлённый в живом коде** (v0.13.0) — на вопросы «актуально ли / что изменилось» внутри git-проекта `/mn:ask` сверяется со свежими коммитами репо и флажит заметки, которые новый коммит мог устаревшить. Опц. code-graph бэкенд через `recall.codeGraph` (Graphify / Sourcegraph / ast-grep…), выключен по умолчанию.
- **Recall со свежестью** (v0.12.0) — `/mn:ask` теперь датирует каждый цитируемый источник (git last-commit если vault под git, иначе mtime файла + frontmatter `reviewed`/`date`) и помечает ответ, опирающийся на устаревшие заметки.
- **Type-aware ревью + контент-линт** (v0.11.0) — `/mn:health` помечает устаревшие заметки по бюджету на **тип** (`review.staleDays`), а не единым «30 дней»; снуз `reviewed:` + per-note `ttl:`; опц. LLM-линт (`review.lint.enabled`) перечитывает кандидатов на устаревшие/противоречащие утверждения — «lint your wiki» Карпати. Changelog переехал в Keep a Changelog v2 + GitHub Releases.
- **Паритет команд Codex/Claude** (v0.10.2–0.10.3) — полные алиасы `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review` в Codex; случайный `/mnemo:mn:*` теперь роутится, а не падает.
- **Autodream-aware индекс памяти** (v0.10.0–0.10.1) — `memory/MEMORY.md` это *тощий* индекс: одна строка `| File | Read when… |` на topic-файл, не абзац. Claude Code жёстко обрезает его на ~24.4 KB при загрузке, поэтому `/mn:health` предупреждает после настраиваемого `memory.indexWarnKB` (дефолт 22). `/mn:ask` теперь вспоминает и из индекса `memory/`, не только из vault.
- **PKM-канон + меньше скиллов** (v0.9.0) — убран `inbox-triage` (**8 → 7 скиллов**): в agent-driven потоке типизированные заметки пишутся напрямую, триажить нечего. Вшиты правила именования (`# . / .md` запрещены), hub-заметки для коротких имён, `metadataCache`-вместо-CLI-кеша для точной проверки ссылок.
- **Dual-runtime** (v0.8.0–0.8.2) — переименование `claude-mnemo` → `mnemo`; нативная поддержка Codex рядом с Claude Code из одного набора скиллов.

Полная история по версиям: [CHANGELOG.md](CHANGELOG.md).

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
codex plugin add mnemo@mnemo
```

В Codex используй короткие алиасы `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review` или полагайся на auto-invocation по описанию. Длинные имена skills (`mnemo:vault-search`, `mnemo:memory-routing`, `mnemo:session-notes`, `mnemo:session-review`) остаются для совместимости. Если случайно набрать `/mnemo:mn:*`, mnemo тоже смаршрутизирует, но каноничный формат — `/mn:*`.

### Первый запуск

```
/mn:health
> Как называется твой Obsidian vault? main
> Сохранено. Запускаю проверку...
```

## Примеры

### Сохранение решений и находок (в любой момент, по ходу)

```
/mn:save "Выбрали PostgreSQL вместо DynamoDB для audit log — лучше JSON querying"
```

Роутит в Obsidian (Atom) + `memory/` (контекст для Claude) + claude-mem (семантический поиск, если включён). Если backend упал — остальные работают.

### Оркестратор конца сессии (единственная команда на закрытие)

```
/mn:review
```

Анализирует сессию, **автоматически** сохраняет решения и создаёт session notes, потом спрашивает про остальное (commit, connect, health).

### Сессионные заметки + handoff

```
/mn:session
```

Создаёт заметку в Obsidian и обновляет handoff для следующей сессии. Больше никакого «а что я вчера делал?»

### Поиск по знаниям

```
/mn:ask "что мы решили по ценообразованию?"
```

Синтезирует ответ из нескольких заметок с цитатами — по vault и индексу `memory/`.

### Скрытые связи

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

Находит связи по концептам, тегам, сущностям. Спрашивает перед применением.

### Аудит vault

```
/mn:health
```

```
📊 Здоровье Vault (2026-04-07)

Всего: 487 заметок
  Atoms: 89 | Molecules: 23 | Sources: 34
  Sessions: 67 | MOCs: 14

🔴 Orphans: 3
🏆 Топ-5 хабов: MOC — Security (34), MOC — AI ML Tools (28)...
```

## Конфигурация

`/mn:setup` или вручную:

```bash
mkdir -p ~/.mnemo
cp config.example.json ~/.mnemo/config.json
```

Все поля опциональны. Скиллы спросят при первом запуске. Полная схема — в `plugins/mnemo/references/config-schema.md`.

## Непрерывность между сессиями

Киллер-фича. `/mn:session` записывает handoff-заметку — следующая сессия подхватывает с того места. Больше никакого «а что я вчера делал?»

## Требования

- [Claude Code](https://claude.ai/code) (Pro/Max/Team или API ключ) **или** [Codex](https://developers.openai.com/codex/skills)
- [Obsidian](https://obsidian.md) (бесплатно) — **должен быть запущен**
- [Obsidian CLI](https://github.com/kepano/obsidian-cli) — `obsidian` в PATH

---

# 中文

## 功能介绍

**mnemo** 为 Codex 和 Claude Code 提供基于 Obsidian 的持久记忆层。七个技能自动处理知识管理的繁琐工作，让你专注于思考。

大多数「第二大脑」工具假设你有时间整理。mnemo 假设你没有。

```
你工作 → mnemo 记住 → Vault 成长 → 你以后能找到
```

### 技能列表

| 技能 | 命令 | 功能 |
|------|------|------|
| **save** | `/mn:save` | 路由级联 —— 将一条事实/决策/发现发送到 Obsidian（+ `memory/`，+ claude-mem 如已启用），优雅降级 |
| **session** | `/mn:session` | 会话摘要笔记 + 跨会话上下文传递 |
| **review** | `/mn:review` | 会话结束编排器 —— 审计会话、自动运行 save + session、推荐其余技能 |
| **ask** | `/mn:ask` | 搜索 vault（+ Claude 的 `memory/` 索引），综合带引用的答案，按时效标注来源，并用项目 git 历史为"当前状态"类回答提供依据 |
| **connect** | `/mn:connect` | 发现笔记之间隐藏的联系 —— 仅建议，不自动应用 |
| **health** | `/mn:health` | Vault 审计：孤立笔记、断链、按类型的复查候选（+ 可选 LLM lint）、增长统计 |
| **setup** | `/mn:setup` | 交互式引导配置 —— vault 名称、分类法、语言 |

### 何时用哪个

| 时机 | 命令 |
|------|------|
| 一出现事实/决策/发现，会话进行中 | `/mn:save` —— 随时保存，**不要囤积**（压缩随时可能丢上下文） |
| 回忆早先上下文 / 过往决策 | `/mn:ask` |
| 刚创建笔记 —— 发现隐藏联系 | `/mn:connect` |
| 工作结束，**或长会话有压缩风险之前** | `/mn:session` —— 写入旅程笔记 + 交接 |
| 结束会话的单一命令 | `/mn:review` —— 审计 + 自动运行 save & session + 推荐其余 |
| 定期 / 创建 3+ 新笔记后 | `/mn:health` |

`save` 和 `session` 互补，而非二选一：`save` **随时**固定离散事实；`session` **在结束时**写入叙事 + 交接。`review` 编排两者 —— 但其自动运行受「重要性判断」门控，所以最稳妥的习惯是：全程 `save` **加上**结束时显式 `session`/`review`。

### 为什么不用 Obsidian 插件？

Obsidian 插件在 Obsidian 内部运行。mnemo 在你的编码代理 —— **Codex 或 Claude Code** —— 内部运行，它可以访问你的整个开发上下文、对话历史和代码库。当你结束一个 3 小时的调试会话时，`/mn:session` 知道你做了什么，因为它全程在场。

### 新特性（v0.14.x）

- **知识复利 + 自我延后的 lint + 研究缺口**（v0.14.0）—— 对 Karpathy "LLM Wiki" 模式做完整审计后提炼出的三个可选、契合理念的增强。`/mn:ask` 可将真正的综合**作为 Molecule 写回 vault**（来源已预先链接），让探索得以累积；`review.lint.autoStampReviewed` 让 lint 给仍然有效的笔记盖上 `reviewed:`，闭合延后回路；`/mn:health` 会提示**研究缺口候选**（笔记众多却无 MOC 的主题、被频繁引用却无 Source 笔记的外部实体）。全部可选：默认安装不写入任何内容（内容 lint 默认关闭），综合写回需用户确认，唯一的自动写入（`reviewed:` 标记）仅在你开启 lint 后才发生。
- **基于实时代码的回忆**（v0.13.0）—— 在 git 项目内回答"是否仍然成立/有何变化"类问题时，`/mn:ask` 会对照仓库最近的提交，标记可能已被新提交过时的笔记。可选代码知识图谱后端 `recall.codeGraph`（Graphify / Sourcegraph / ast-grep…），默认关闭。
- **带时效的回忆**（v0.12.0）—— `/mn:ask` 现在为每个引用来源标注更新时间（vault 是 git 仓库则用 git last-commit，否则用文件 mtime + `reviewed`/`date` frontmatter），并标记基于陈旧笔记的答案。
- **按类型的复查 + 内容 lint**（v0.11.0）—— `/mn:health` 按**类型**预算（`review.staleDays`）标记陈旧笔记，而非统一的 30 天；`reviewed:` 缓刑 + 单笔记 `ttl:`；可选 LLM lint（`review.lint.enabled`）重读候选以发现过时/矛盾的声明 —— Karpathy 的 "lint your wiki"。Changelog 迁移到 Keep a Changelog v2 + GitHub Releases。
- **Codex/Claude 命令对等**（v0.10.2–0.10.3）—— Codex 上完整的 `/mn:ask`、`/mn:save`、`/mn:session`、`/mn:review` 别名；误输入的 `/mnemo:mn:*` 现在会被路由而非报错。
- **Autodream 感知的记忆索引**（v0.10.0–0.10.1）—— `memory/MEMORY.md` 是*精简*索引：每个主题文件一行 `| File | Read when… |`，而非段落。Claude Code 在加载时会在 ~24.4 KB 处硬截断，因此 `/mn:health` 会在可配置的 `memory.indexWarnKB`（默认 22）之后警告。`/mn:ask` 现在也从 `memory/` 索引回忆，不只是 vault。
- **PKM 规范 + 更精简的技能集**（v0.9.0）—— 移除 `inbox-triage`（**8 → 7 个技能**）：在代理驱动的流程中，类型化笔记被直接写入，没有需要分类的收件箱。内置笔记命名规则（禁用 `# . / .md`）、短名称的 hub 笔记、用 `metadataCache` 而非 CLI 缓存进行准确的链接检查。
- **双运行时**（v0.8.0–0.8.2）—— 更名 `claude-mnemo` → `mnemo`；从同一套共享技能原生支持 Codex 与 Claude Code。

完整逐版本历史：[CHANGELOG.md](CHANGELOG.md)。

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
codex plugin add mnemo@mnemo
```

Codex 支持短别名 `/mn:ask`、`/mn:save`、`/mn:session`、`/mn:review`，也可以按 description 自动触发。长 skill 名称（`mnemo:vault-search`、`mnemo:memory-routing`、`mnemo:session-notes`、`mnemo:session-review`）仍保留兼容。误输入 `/mnemo:mn:*` 也会被路由，但规范格式是 `/mn:*`。

### 首次运行

```
/mn:health
> 你的 Obsidian vault 名称是？ main
> 已保存。正在运行健康检查...
```

## 使用示例

### 保存决策与发现（随时，边做边存）

```
/mn:save "选择了 PostgreSQL 而不是 DynamoDB 用于审计日志——JSON 查询更好"
```

路由到 Obsidian（Atom 笔记）+ `memory/`（Claude 的未来上下文）+ claude-mem（语义搜索，如已启用）。任何后端宕机，其他仍然工作。

### 会话结束编排器（结束会话只需这一个）

```
/mn:review
```

分析会话，**自动**保存决策并创建会话笔记，然后询问其余操作（commit、connect、health）。

### 会话笔记 + 交接

```
/mn:session
```

在 Obsidian 中创建会话摘要，更新下次会话的交接文件。

### 知识搜索

```
/mn:ask "我们对定价策略做了什么决定？"
```

从多个笔记中综合答案，附带引用 —— 跨 vault 与 Claude 的 `memory/` 索引。

### 发现隐藏联系

```
/mn:connect "Atom — LongCat-Flash-Prover"
```

通过概念、标签、实体找到关联。应用前会询问确认。

### Vault 审计

```
/mn:health
```

```
📊 Vault 健康报告 (2026-04-07)

总计：487 个笔记
  Atoms: 89 | Molecules: 23 | Sources: 34
  Sessions: 67 | MOCs: 14

🔴 孤立笔记：3
🏆 前5大枢纽：MOC — Security (34), MOC — AI ML Tools (28)...
```

## 配置

`/mn:setup` 或手动：

```bash
mkdir -p ~/.mnemo
cp config.example.json ~/.mnemo/config.json
```

所有字段可选。技能会在首次使用时询问。完整 schema 见 `plugins/mnemo/references/config-schema.md`。

## 跨会话连续性

杀手级功能。`/mn:session` 写入交接笔记，下次会话自动接续。再也不用问「我昨天在做什么？」

## 环境要求

- [Claude Code](https://claude.ai/code)（Pro/Max/Team 或 API 密钥）**或** [Codex](https://developers.openai.com/codex/skills)
- [Obsidian](https://obsidian.md)（免费）——**必须运行中**
- [Obsidian CLI](https://github.com/kepano/obsidian-cli)——`obsidian` 命令在 PATH 中

---

Made with care by [Claude Code](https://claude.ai) + [jojoprison](https://github.com/jojoprison)
