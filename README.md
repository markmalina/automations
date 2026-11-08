# automations
n8n configuration and service automations: Work uploads, GitHub, Gate and Telegram.

## n8n — заморожен по поручению владельца

Статус на 08.11.2026, 17:54 МСК: **FROZEN_BY_OWNER**. Низкий приоритет. Разработка, деплой, тестовые установки, новые CI, мониторинг поддержки и расписания не возобновляются автоматически. Даже ответ OpenAI Support не снимает заморозку: требуется новое прямое поручение Марка.

Единственная очередь и checkpoint: https://github.com/markmalina/automations/issues/14 .
Product #1 и S1 #9 остаются открытыми и приостановленными; пользовательский live-результат не достигнут.

### Сохранённая работа

Принятый code baseline: [509a25452889a24afef5f1c1edc2fcfba1e55b7e](https://github.com/markmalina/automations/commit/509a25452889a24afef5f1c1edc2fcfba1e55b7e).
Код, тесты, bootstrap/workflow exports и отчёты находятся в Git:
- [100 файлов / 30 МБ, локальный native case](docs/sprints/S3N-2026-11-08/REPORT.md);
- [перезапуск и журнал](docs/sprints/S3R-2026-11-08/REPORT.md);
- [отказ неверного разрешения](docs/sprints/S3G-2026-11-08/REPORT.md);
- [восстановление после потери ответа](docs/sprints/S3L-2026-11-08/REPORT.md).
Это local n8n + synthetic GitHub evidence, не deploy/live acceptance.
[Пакет прежнего блокера](https://github.com/markmalina/automations/issues/9#issuecomment-6715607237).
[Исследованные альтернативы MCP-плагина](https://github.com/markmalina/automations/issues/14#issuecomment-6718664505) остаются предложениями, не разрешением на реализацию.
Старые draft PR #2–5 и их ветки сохранены, не объединены и не удалены.

### Проверка остановки

Три собственные ChatGPT-автоматизации проверены: disabled, next run отсутствует, последние исполнения completed:
- Automation_45158fef76248191b075a7e96d9665f0 — контроллер;
- Automation_303e1627b4e48191b93deb79a403c290 — исполнитель;
- Automation_ddc69faaf3748191aa5ae702a125b786 — финальный отчёт.
Соседние проекты и расписания не менялись.

GitHub Actions: in_progress=0, queued=0. В трёх существующих workflow нет cron/schedule: source CI реагирует на изменения tools/CI, диагностические jobs — только на точные команды владельца. README-only фиксация заморозки не попадает в source CI path filters. Условия проверок не менялись и проверки не запускались.

Существующий Railway pilot / n8n-upload: replicas running=0,total=1, cronJob=null. Последнее развёртывание d7469a53-374f-4c5f-a5d8-beed4c086847 от06.11; metadata Online/SUCCESS не означает работающий процесс.
Метрики за последний час,13 samples: CPU current/avg/min/max=0; MEMORY_USAGE_GB current/avg/min/max=0.
**Хранение остаётся:** DISK_USAGE_GB=0.794165248; volume /data1024MB сохранён. Storage может тарифицироваться; полный счёт/фактическое списание неизвестны. «Ноль расходов вообще» не заявляется.
Дополнительные Railway API инвентаризации automation/agent tasks вернули INVALID_ARGUMENT; отсутствие дополнительных внутренних Railway automation/agents этими вызовами не доказано. Известные ChatGPT cycles и остановка самого n8n проверены отдельно.

Свои временные runtime/DB/keys/grants/fixtures/rawlogs/public npm cache ранее очищены; свежая проверка известных task32/night08/oldtask17 paths — отсутствуют, ps по собственным n8n/probe/cache paths —0.
Локальных Git checkout в проверенных собственных рабочих каталогах не обнаружено; подтверждённый опубликованный код в remote сохранён. Это не аудит произвольных чужих Work.
Служебная persistent БД/журнал/OAuth не публикуются в public repo. Они остаются на сохранённом volume. Старый failed upload ID и pending patch0bfc3cd0-278a-4e41-b1f1-7df8cb385602 не удалены и не применены. Отказанный Deploy не повторялся и не обходился.

### Возобновление

Только после нового прямого поручения владельца: перечитать свежую очередь, проверить фактическое состояние и выбрать направление. Не применять старый pending patch как текущий release и не запускать прежние ночные циклы автоматически.
