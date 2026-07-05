# mnemo 1.1.0 — проактивные /mn:ask + /mn:save (state)

Ветка: `feat/proactive-skills-1.1.0` · воркти: proud-stargazing-canyon · старт 2026-07-05
Цель: агент САМ (mid-task, по смыслу) зовёт /mn:ask (recall перед действием) и /mn:save (сохранить важное), не только по явной команде юзера. Полный разбор: `memory/mnemo-proactive-roadmap.md` + Obsidian `Molecule — проактивные mn-ask и mn-save…`.

**Governance:** это minor → 1.1.0 → апрув j получен 2026-07-05 («го на всё»). Финальный бамп манифеста — после trigger-eval-гейта.

## RIGHT NOW
- focus: аудит скиллов (skill-creator гайд, 10 агентов) ГОТОВ + дешёвые фиксы применены → P1 (hooks + тела + остаток аудит-фиксов)
- audit-итог: все скиллы minor-gaps, 0 blockers; массово хорошо (imperative 9/9, gotchas 7/7, RU 7/7, why>ALLCAPS 8/9, тело<500 9/9); свежие descriptions НЕ переборщили (3 overtrigger-риска → под eval P2, не резать).
- audit-фиксы ПРИМЕНЕНЫ (this wave): M5 bare `references/`→`${CLAUDE_PLUGIN_ROOT}/references/` (7 скиллов, реальный баг — не резолвились); M1 session-review порядок save→session (было противоречие Rules vs Step7); m4 commands/mn/save.md desc актуализирован (.claude/rules v0.15.0). lint exit 0.
- audit-фиксы ВОЛНА 2 ПРИМЕНЕНЫ (все кроме m1): M2 session-notes Codex-fallback (нет safe CLI-create → graceful в ~/.codex/memories/ + CODEX_SESSION_ID; путь помечен Claude-primary); M3 memory-routing claude-mem POST→`scripts/claude-mem-save.sh` (python JSON-safe, экранирует кавычки/бэктики/$(); гоча v12.3.9 закодирована); M4 initial-setup taxonomy JSON для PARA/Custom + session/moc как функциональные типы; m3 $0-fallback→glob (session-review:91 + session-notes template); m5 session-notes shorthand-why (banned/mandatory); vault-health desc +lead-фраза; initial-setup desc honesty (language→links-section language, integrations→defaults). memory-routing/vault-health RU-слова НЕ резал (j явно просил, аудит §4 «не вредит»). lint 15/15, скрипт bash-n+JSON-тест OK, session-scan graceful.
- ОСТАЛОСЬ minor: m1 (дубли правил session-review:233-247 — источник дрейфа, но само противоречие M1 устранено; чистка отложена, риск>выгода в спешке).
- last: workflow 5 агентов подтвердил идеальную структуру. Применено: 8 алиасов `skills/{mn-*,mnemo-mn-*}` → `user-invocable:false` (к disable-model-invocation:true) = «Hide individual skills», уходит дубль автокомплита. Каноны/команды уже верны. lint exit 0. Честная поправка: user-invocable:false бюджет НЕ чистит (его чистит disable-model-invocation, уже стоял) → выгода правки = только /-menu дубль.
- next: 2 ГЕЙТА на j перед мержем 1.1.0: (1) перепрогнать /doctor на обновлённом плагине; (2) Codex-probe (игнорит ли user-invocable). Оба зелёные → можно к P1 (hooks+тела) и потом релиз.
- gate-status: descriptions+visibility готовы; trigger-eval (P2) ещё не прогнан.
- 🧭 РЕШЕНИЕ j (2026-07-05): НЕ дробить релиз. Делаем 1.1.0 ЦЕЛИКОМ (descriptions+visibility + P1 хуки+тела + P2 eval), один релиз. НЕ релизить промежуточно. Порядок: дождаться аудита скиллов (workflow wu8ng2o16) → применить фиксы + P1 тела (одной волной) → P1 хуки → P2 trigger-eval гейт → релиз 1.1.0 (апрув на тег). /doctor юзер проверит ПОСЛЕ релиза+update.

## Acceptance (Definition of Done для 1.1.0)
- GIVEN проактивный сценарий (агент перед фиксом бага / после решения бага) WHEN агент рассуждает THEN он сам зовёт /mn:ask resp. /mn:save (не ждёт команды юзера).
- Trigger-eval (P2, ГЕЙТ релиза): `skill-creator` методика, 60/40 позитив/near-miss негативы («найди в коде X» ≠ recall, «поищи в интернете» ≠ vault). Проактивные позитивы срабатывают, негативы — нет. Результаты в `docs/TESTING.md`.
- Для SessionStart/Stop-нуджа — ОТДЕЛЬНЫЙ eval на lift частоты проактивного вызова ПОВЕРХ голого description. Нет lift → нудж не шипим.
- lint-skills.py exit 0; dual-runtime цел (тела Codex-safe); descriptions-бюджет не раздут (см. /doctor).

## P0 — descriptions + скрытие алиасов (frontmatter only, тела не трогаем) — ✅ ГОТОВ (lint green)
- [x] vault-search: +агент-ситуации ВПЕРЁД (перед фиксом бага/незнакомая подсистема/рискованное действие) + «or similar» + RU-хвост. 431→675
- [x] memory-routing: +«proactively, without being asked — solved a bug / non-obvious decision / gotcha» вперёд рамки «user says». 572→648
- [x] session-notes: +mid-task checkpoint (обновляет ту же заметку+handoff, НЕ дубль) + RU «сохрани сессию/handoff». 330→487
- [x] session-review: ТОЧЕЧНО — убран голый триггер `'review'` (коллизия code-review). НЕ переписан под «Use proactively». 405→406
- [x] vault-health: +RU (сироты/битые ссылки/здоровье базы); «weekly» → «checks haven't run in a while». 319→415
- [x] link-discovery: +RU (найди связи/перелинкуй) + цепочка «right after mn:save/mn:session». 337→441
- [x] initial-setup: +RU (настрой мнемо) + «or similar». 391→420
- [x] aliases ×8: `disable-model-invocation: true` — подтверждён docs/en/skills:350 (юзер слэшем зовёт, модель не авто, description уходит из контекста). ⚠️ Codex: прогнать — игнорит поле → укоротить алиасы вручную (алиасы уже короткие 88-111)
- [ ] `/doctor` (ПРОСИТЬ j — интерактивная, сам не запущу): зафиксировать реальный eviction ДО вывода про бюджет
- [x] lint exit 0; бюджет модели 3660→3492 (net −168)

## P1 — механика (детерминизм) + тела скиллов
- [ ] РАСШИРИТЬ `plugins/mnemo/hooks/hooks.json` (не создавать!): +синхронный SessionStart (matcher `startup|resume|clear|compact`) рядом с async prewarm — prewarm СОХРАНИТЬ. +Stop (non-blocking additionalContext, губернатор молчит по умолчанию)
- [ ] `hooks/codex-hooks.json` (в репо НЕТ) — только Stop/SessionStart; **прогнать Codex живьём** (потребляет ли plugin-hooks — гипотеза)
- [ ] PreCompact — пометить Claude-only (Codex не имеет события); save-паритет на Stop
- [ ] ОДИН always-on канал: SessionStart-инжект (факты-не-приказы, гейт на config+нетривиальность). БЕЗ строки в коммитимый CLAUDE.md (дубль + cross-link violation)
- [ ] vault-search тело: ветка «agent-initiated → derive query, don't ask user» + анти-луп «once per topic per session» + gotcha «no prior context → one line, return to task»
- [ ] memory-routing тело: worth-saving гейт (Step 0: «только если future session поступит иначе») + save→connect offer + NOOP-исход + secrets `<REDACTED>` + governor-лестница
- [ ] session-notes тело: mid-task checkpoint dedupe by session id + handoff
- [ ] initial-setup: `cascade.project_rules: {enabled:true}` в Step 5 JSON (расходится с config-schema.md:43)

## P2 — фиксы + eval-гейт
- [ ] session-review: memory-index путь Step 1 (`$HOME/.claude/projects/<encoded-cwd>/memory/`), REF_DIR path-cascade для Codex
- [ ] plugin-wide `references/…` → `${CLAUDE_PLUGIN_ROOT}/references/…`
- [ ] trigger-eval (ГЕЙТ) + SessionStart-lift eval → `docs/TESTING.md`
- [ ] bump 1.1.0 (3 манифеста) + CHANGELOG + tag + Release + `/plugin update`

## Отвергнуто осознанно (не реализовывать)
PreToolUse(Read) auto-recall (нужен индекс/демон); UserPromptSubmit-нуджи (цена/промпт); блокирующий Stop (лупы у чужих юзеров); per-model ветвление промптов (ломает dual-runtime); новый скилл «memory-protocol» (−бюджет, plugin-агентам хуки запрещены); awareness-строка в CLAUDE.md.
