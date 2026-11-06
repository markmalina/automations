# Работа с Automations

- Назначение: конфигурация n8n и проверяемые процессы взаимодействия сервисов Марка Малиновского.
- Первая задача: tools/n8n-github-upload, issue #1, отдельная infra/work-github-upload; до приёмки не менять текущий способ загрузки.
- Не менять Gate, существующие Telegram Webhook, другие Railway projects/services, баннеры Dreame без отдельного поручения.
- Для штатной передачи файлов/Git дополнительная LLM и Railway Agent не нужны.
- Секреты не выводить в переписку/логи и не сохранять в Git. Экспорты workflows должны быть без значений credentials. Автоматические внутренние преобразования разрешены; байты файлов не передавать через модель.
- Разрешён ограниченный пилот до $1 и двух часов compute. PILOT_DEADLINE_MS — абсолютный срок; не продлевать автоматически. После пилота остановить compute, проверить состояние. Долговременная работа требует решения владельца.
- Отчёт разделяет подготовку, реальное выполнение и ещё не пройденную приёмку. Проверять подтверждённый push, SHA-256 и отсутствие дубликатов, не выдавать HTTP 200 за полную готовность маршрута.
- История переноса: freelance issue #8 / draft PR #9; исходные исследования там сохраняются.

## Ops: подключение n8n Upload

- Кандидат подключения: Ops #434 / draft PR #435; локальная инструкция tools/n8n-github-upload/OPS_ONBOARDING_2026-11-06.md.
- agent-ops.lock и .agent-ops/project.yml допускают только provider-free onboarding-preflight; это не разрешение на apply.
- Точный клиентский workflow .github/workflows/ops-n8n-preflight.yml закрепляет полный Ops SHA. Команда /n8n-ops preflight на issue #1 возвращает ABORTED/E_NOT_RELEASED до приёмки живого маршрута.
- Не подменять отсутствующий n8n executor существующими Gate/AQUB действиями, не копировать их credentials. Кандидат не включает provider/secret access и не служит обходом отклонённого deploy.

## Ops: read-only inspection candidate

- Команда /n8n-ops inspect на issue1 подготовлена отдельным workflow; до merge/main и read-release acceptance обработчик не установлен.
- agent-ops.read.lock и .agent-ops/read-project.json закрепляют точный Ops SHA, target, read operation и release bytes.
- Первый job без provider secrets. Protected job n8n-upload-readonly допускается только после отдельно принятого read-release; сейчас OFF, E_READ_NOT_RELEASED до чтения секрета.
- Имена protected Environment и N8N_UPLOAD_RAILWAY_PROJECT_TOKEN — только предполагаемые bindings: их создание и наличие не подтверждены. Не использовать Gate/AQUB/shared credentials.
- Диагностика не применяет/удаляет staged patch и не снимает прежний отказ deploy. HTTP200 не подтверждает runtime hashes/disk/journal/persistent mode.
