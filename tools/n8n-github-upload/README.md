# Work → n8n → GitHub

**Статус 06.11.2026: сквозной пилот проверен, производственный маршрут ещё не принят.**

Репозиторий разработки: `markmalina/automations`, ветка `infra/work-github-upload`, [issue #1](https://github.com/markmalina/automations/issues/1), [draft PR #2](https://github.com/markmalina/automations/pull/2). Исходное исследование: freelance #8 / PR #9; Dreame и #7 не затрагиваются.

Актуальные доказательства: [первый Git-пилот](GIT_ACCEPTANCE_2026-11-06.md), [повторы и MCP](RETRY_ACCEPTANCE_2026-11-06.md). Старые отчёты описывают состояние на указанное в них время.

## Фактически работает в пилоте

- Команды и исходящий HTTPS из текущего обычного Work, без Codex Cloud-задачи и скачивания на телефон.
- Защищённый Webhook, multipart, отдельные файлы; ZIP и Base64 через модель не используются.
- Штатные Webhook, Crypto, Write Files, Git, HTTP Request, JWT и Execute Command n8n.
- Один бинарный файл, 100 смешанных файлов / 30 МБ, кириллица, пробелы, вложенные пути; скачивание и проверка SHA-256.
- Один commit/push на комплект, обновление ровно одного существующего файла без удаления остальных.
- Журнал на постоянном диске: повтор после сбоя за push, после restart, после удаления тестовой рабочей копии и при одновременных запросах возвращает прежний SHA.
- Штатный MCP фактически ответил `tools/list`, принял JSON и выдал разрешение на загрузку, привязанное к хешу полного manifest. Разрешение действует 10 минут; в SQLite хранится только хеш его токена.
- Отдельный проверенный процесс выпускает свежий GitHub App installation token перед каждым запросом штатными JWT/HTTP Request; Git использует его через expression credential.

## Где работает

Один отдельный `n8n-upload` service и один persistent volume 1 ГБ в существующем Railway Hobby workspace; SQLite, без PostgreSQL/Redis/VPS и новой подписки. Образ `docker.n8n.io/n8nio/n8n:2.46.6`, Git 2.55.0, Node 24.22.1; лимиты 1 ГБ RAM / 0.5 vCPU / одна replica.

HTTPS: `https://n8n-upload-pilot.up.railway.app`. Тестовая цель жёстко ограничена `markmalina/freelance`, веткой `test/n8n-upload-20261106`; `main` не меняется. GitHub App установлен на все текущие и будущие репозитории владельца, но это ещё не универсальный интерфейс загрузки: тестовый token дополнительно ограничивается freelance.

`/data/.n8n` содержит SQLite n8n и encrypted credentials. `/data/work/control/uploads.sqlite` — отдельный локальный журнал операций. Рабочие копии — `/data/work/git/pilot-<uploadId>`, binary staging — `/data/work/uploads`. Всё на одном persistent volume. После restart n8n читает SQLite/credentials и журнал; после подтверждения коммита тестовую копию можно удалить. Повтор сверяет достижимость SHA на GitHub и не требует старой копии. Новая загрузка клонирует репозиторий заново. Потеря самого volume пока не покрыта проверенным backup/restore.

## Как продолжить

1. Прочитать [инструкцию следующему Work](WORK_USE.md) и актуальный отчёт.
2. Завершить разовое подключение ChatGPT → n8n через OAuth с `workflow:read`, `workflow:execute`, `execution:read`. Форма подготовлена; создание/consent ещё не подтверждены. Постоянные секреты в Work передавать не требуется.
3. Проверить независимый новый Work из Android, обновление OAuth после истечения access token и restart подключения. Нельзя обещать отсутствие переподключений до этой проверки.
4. Завершить универсальную адресацию репозитория/ветки/папки, безопасное восстановление незавершённого commit/push, проверки путей/атрибутов Git, понятные HTTP-коды отказов, резервное копирование и режим постоянной работы.

Текущий способ загрузки остаётся рабочим до полной приёмки. Пилот разрешён до $1 и суммарно двух часов compute; постоянная работа ещё не согласована. Запущенный n8n занимает RAM в простое; сон и пробуждение для этого процесса не проверены. Диск продолжает тарифицироваться после остановки compute.

## Основные файлы

- `fresh-token-upload-probe.workflow.json` — проверенный bounded-процесс с новым installation token на запрос.
- `upload-grant.workflow.json` — только выдача разрешения, опубликован для MCP; HTTP-вход отдельно требует private pilot Header Auth.
- `git-retry-probe.workflow.json` — воспроизводимый сбой после push и повторы.
- `upload-ledger.cjs`, `test_upload_ledger.py` — транзакционный журнал метаданных и проверки гонок/срока разрешений; это не HTTP-загрузчик.
- `run_granted_probe.py`, `mcp_probe.py`, `verify_git_probe.py` — диагностические клиенты; локальные credentials исключены из Git. Personal MCP API key использован только для диагностического клиента, не является настройкой будущих Work.
- `railway-live-configuration.json`, `pilot-bootstrap.cjs` — развёртывание без секретных значений.
