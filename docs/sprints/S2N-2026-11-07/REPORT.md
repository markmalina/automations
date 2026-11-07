# №17 — native binary: UNAVAILABLE на подготовке среды

07.11.2026,18:04 МСК. Исполнитель завершил ограниченный проход; требуется приёмка контроллером.
Задача: https://github.com/markmalina/automations/issues/17
Очередь: https://github.com/markmalina/automations/issues/14
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md

## Результат

**UNAVAILABLE / E_NATIVE_SETUP_BUDGET.** Настоящий binary workflow, local GitHub protocol,
receipt/replay и независимая проверка stub bytes не запускались. Это не FAIL исходников
n8n/workflow и не PASS интеграции. Непригодность n8n как выбранного решения не установлена.

Задача ограничивает подготовку среды первыми8мин. Начальный clock execution:
17:55:12МСК; в18:03:12 установка прервана через управляющий инструмент.
Получен terminal exit130. Одной CLI версии недостаточно для готовности движка:
после остановки SQLite native binding отсутствовал, установка не завершилась,
package-lock.json не был создан. Отсутствие binding — установленное состояние
подготовки; его точная первопричина в этом проходе не установлена.
Сетевой запрет, ошибка TLS, npm dependency conflict или окончательный отказ сборки
по этим данным не доказаны. В сохранённом install output npm error code отсутствует.

## Что фактически проверено

| Наблюдение | Результат |
| --- | --- |
| Node/npm |24.22.1 /11.9.0 |
| n8n/Docker до установки | отсутствовали в PATH |
| Изолированный prefix | собственный native17, mode0700 |
| Единственный install | n8n@2.46.6; terminal130 после остановки по setup budget |
| Реальный CLI --version |2.46.6 |
| package metadata | n8n2.46.6, n8n-nodes-base2.46.6 |
| SQLite node binding после остановки | отсутствует |
| Полный install/lock/integrity dependency tree | не подтверждены |
| Owner setup / native engine start | не выполнялись |
| Native binary / stub requests / replay | не выполнялись |
| Реальные grant/upload/GitHub/Railway | не выполнялись |

Наличие package metadata и CLI2.46.6 не объявляется доказательством полной/исправной
установки или эквивалентности Railway image. Не подменялись native execution
запуском прежних unit tests, JSON import или fake transport.

## Source и воспроизведение подготовительного препятствия

Fresh source/main: c6654f96a64b63ed0ef0ffa8c27b0b8c411bba9d.
Применимых AGENTS.md/WORK-PARENT.json в дереве не обнаружено.
Claim/PR/jobs проверены перед принятием: конкурирующего writer/outcome не было.
Прочитаны #17, fresh queue, план, WORK-RULES, runtime/package/network instructions
и ограниченный отчёт #13. Принятые #10/#12/#13/#15 не повторялись.

Три S1 source bytes совпали с опубликованным exact candidate2e7643bd805840f5ddba4d9836a8caf8fc6f508d:

| Файл | SHA-256 |
| --- | --- |
| upload-ledger.cjs |81a4b3af7a15fe165fb7ca41b73dd228eb2ec57826b422064f2f40dc974f4401 |
| upload-grant.workflow.json |8bf95f9e993e4ff494ad3cf90e86e694194366cb18c85496ec4e3abba9b3ff43 |
| owner-repository-upload.workflow.json |ae983561ed594a4fe0971c5b8b6be3a16eb87ac40311883d5ee7f34ed55a9c18 |

В собственной0700папке выполнена одна команда:

```sh
npm install --prefix "$task_dir" --save-exact n8n@2.46.6 --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000
```

Унаследованные proxy/CA сохранены; их значения не выводились.
Startup /etc/codex/network-policy.json отсутствовал. Sidecar/direct обходов,
отключения TLS, нового install, системного daemon или ручной native сборки не было.
После появления CLI выполнен один bounded20s --version, завершившийся2.46.6.
До этого npm cache metadata для n8n/n8n-nodes-base/sqlite3 были видимы;
это не означает готовность полного offline cache или ранее удалённого runtime #13.

В scratch были подготовлены локальный stub и orchestrator, пройдена только
py_compile. Они не исполнялись и удалены; непроверенный harness не публикуется как
готовое решение или новая тестовая платформа. В этой ветке сохранён только отчёт,
production source неизменён. Hosted CI для evidence-only Markdown не нужен;
зелёных checks и новых тестов этот отчёт не заявляет.

## Terminal boundary и остаток

Install session закончилась exit130, без повторов. n8n/stub server/runner не запускались;
runtime folder, keys, credentials, grant, fixture payload и SQLite не создавались.
Собственный prefix с частичной установкой/source/logs/scripts/cache удалён;
итог удаления подтверждается отдельно terminal receipt в #17.
Общий npm cache не очищался, HOME не переназначался.

Railway/реальные credentials/permissions/pending/old failedID/journal/S1/server
и соседние проекты не читались и не менялись. Реальные OAuth/MCP/grant/upload не вызывались.
Текущая пользовательская загрузка остаётся непринятой, S1 blocked не снят.

Достаточный вход для продолжения той же #17: доступный exact n8n2.46.6 native runtime
с рабочим SQLite и согласованным bounded setup либо уточнённый controller budget.
Истечение claim не разрешает параллельного writer; этот execution после cleanup
terminal и не продолжает установку за пределами setup budget. Новую задачу исполнитель
не создаёт, merge/закрытие #17 не выполняет.

ДАЛЬШЕ: контроллер — принять ограниченное UNAVAILABLE свидетельство и решить продолжение #17.
