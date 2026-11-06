# Повторы, журнал и MCP — 06.11.2026

Статус: **пилот проверен; полная производственная приёмка не завершена**. Разработка — automations #1 / draft PR #2, ветка infra/work-github-upload. Выполнено по поручению «Делай» в том же обычном Work. Старый способ загрузки сохранён.

## Выполнено

Один существующий Railway service n8n/SQLite/volume сохранён. Ни отдельного сервера, ни PostgreSQL/Redis, ни подписки, ни LLM не добавлено. Выполнена новая ограниченная итерация; deadline 17:00 МСК, в пределах прежнего $1 и суммарных двух часов compute. Пилот далее остановлен отдельной подтверждаемой операцией; факт остановки — retry-pilot-stop-proof.json.

Приём binary, multipart, hashing, запись файлов, clone/commit/push и API GitHub выполняются готовыми узлами n8n. Добавлен только локальный журнал метаданных upload-ledger.cjs, использующий стандартный Node node:sqlite: WAL, synchronous=FULL, BEGIN IMMEDIATE, PRIMARY KEY upload ID. Содержимое файлов и Git-команды этот модуль не принимает/не реализует. У проверенного DataTable upsert есть транзакция update-then-insert, но проверенный интерфейс не предоставляет уникальный пользовательский ключ upload ID; обычный read/write receipt также не является атомарным захватом. Вместо отдельного DB service использована библиотека SQLite, уже имеющаяся в образе. Не утверждается отсутствие всех возможных решений n8n: это минимальная реализация журнала для текущего single-service пилота.

Журнал связывает ID с SHA-256 canonical manifest. Иной manifest с тем же ID отклоняется. После commit SHA сохраняется до push; после push проверяется достижимость commit на целевой ветке через GitHub compare. Success/receipt записывается только после этой проверки. Повтор известного commit не выполняет clone/commit/push. Если процесс остановился до записи SHA, состояние uncertain не сбрасывается и второй commit автоматически не создаётся.

Штатный MCP включён, autoExposeNewWorkflows=false. Для MCP опубликован только workUploadGrantPilot. Он принимает компактный JSON {id,digest,fileCount,totalBytes}, выдаёт случайное 256-bit разрешение на 10 минут, хранит только SHA-256 его токена. Фактический tools/list: 55 tools под диагностическим personal API key; схемы execute_workflow/get_workflow_execution сохранены, openai/fileParams отсутствует. Bytes идут затем по HTTPS, без MCP-file input и без Base64 через модель.

Отдельный fresh-token-upload-probe.workflow.json штатным JWT node подписывает GitHub App JWT из encrypted credential, штатным HTTP Request получает новый installation token с repository_ids=[1378687935] и contents:write перед каждым запросом. Git credential содержит expression на результат узла, а не выданный навсегда token. В двух запросах зафиксированы разные expiresAt; выпуск токена на запрос доказан реальным Git push и последующим compare. Часовое ожидание до истечения токена не проводилось, но старый сохранённый installation token этот процесс не использует.

## Проверено фактически

| Проверка | Результат | Доказательство |
|---|---|---|
| 16 одновременных транзакционных захватов одного ID | Только один new, остальные uncertain; другая привязка отклонена | ledger-local-verification.json; test_upload_ledger.py |
| Сбой после реального push, до подтверждения | Первый запрос намеренно HTTP 500; повтор вернул прежний SHA 41bb4b3c66f587f5e0d5aae00c6904c55d7edc03, replayed=true | retry-after-push*.json |
| Перезапуск контейнера после сохранения результата | Повтор того же ID снова вернул тот же SHA | deployment 4282bdc3… → fa6f10f1…; retry-after-push-replayed.json |
| Удаление подтверждённой тестовой копии и продвижение ветки другими комплектами | Повтор старого ID вернул прежний SHA, достижимый на новой вершине, без нового commit | retry-cleanup-receipt.json, retry-after-later-commits.json |
| Изменённый manifest при прежнем ID | Отклонён до Git | retry-after-push-conflict.json |
| Закрытие клиентского соединения после отправки body | Клиент response не читал; первый последующий запрос выполнил новую загрузку, следующий вернул replay | retry-disconnect*.json. Нельзя утверждать, что исходный оборванный запрос успел завершиться на сервере |
| MCP get details → execute → get execution | execution 18, 25 и 30 success, возвращён bound grant, значение токена не опубликовано | mcp-grant-proof.json; mcp-upload-tool-schemas.json |
| Неверное разрешение | HTTP 500, загрузка не выполнена; код отказа ещё требует улучшения | granted-upload-wrong.json |
| Правильное разрешение → private GitHub | SHA 311331694c30903cf82d3e5e729bdf76ca3f9931; скачанный BIN совпал | granted-upload-upload*.json |
| Два одновременных HTTP запроса одного нового комплекта, свежий App token на запрос | Оба success, один replayed=false, второй replayed=true, один SHA 685f932c7109b1ba656eaaae84cb9aa6099d6439 | concurrent-a-upload.json, concurrent-b-upload.json; independent history proof |
| 100 файлов / 30 000 000 байт через grant + свежий App token | Один SHA 9c9e4a262de79ac9bd35bab14121ae8fd09b598b, ровно 100 added paths, один родитель, ZIP не использовался | grant-batch-100-upload.json; retry-remote-history-proof.json |
| Все 100 файлов скачаны по точному SHA | Все 100 SHA-256 совпали, кириллица/пробелы/вложенность сохранены | grant-batch-100-upload-verified.json |
| Повтор полного комплекта | Тот же SHA, replayed=true, без второго commit/push | grant-batch-100-repeat-upload.json |

Независимый GitHub connector прочитал пять последовательных commits от исходной вершины 9f22ef…: 41bb4b3… → eb98511… → 3113316… → 685f932… → 9c9e4a2…. Каждый соответствует отдельному upload ID. Повторные запросы не добавили commit. Новые комплекты расположены в разных n8n-retry-tests/<uploadId>, их пути не смешались. Update-only и исходный PNG/100 файлов отдельно доказаны в GIT_ACCEPTANCE_2026-11-06.md; в этой итерации пользовательские файлы не обновлялись, main не менялась.

## Время и ресурсы

| Операция | Полное время HTTP | Обработка от Prepare upload | Узел push |
|---|---:|---:|---:|
| 100 файлов, новый процесс | 37.716749 s | 20.305 s | 2.392 s |
| Повтор 100 файлов | 72.281301 s | 1.397 s | Не вызывался; receipt хранит время первоначального push |
| Скачивание 100 файлов для проверки, успешная попытка | 9.941070 s | Не измерено отдельно | Не применимо |
| Одновременный запрос, создавший commit | 24.722433 s | 18.762 s | Не выделено в этом раннем receipt |
| Одновременный запрос, вернувший replay | 27.336330 s | 0.923 s | Не вызывался |

37.72 s — от начала multipart HTTP до подтверждённого remote commit; время отдельной выдачи grant и ручные промежутки между диагностическими вызовами в число не входят. Client send() на 30 MB занял 5.787948 s, но это передача в TLS/socket/proxy, не серверное подтверждение последнего входящего байта. Отдельное точное ingress-время n8n не измерено. Разница total/processing включает сеть, TLS, multipart parsing и очередь — нельзя называть её только передачей файла.

Первая попытка скачивания нового полного комплекта завершилась HTTP 500/socket close в HTTP Request; повтор прошёл и дал все 100 совпадений. Повторная загрузка выполнялась во время ожидания предыдущего verification workflow при N8N_CONCURRENCY_PRODUCTION_LIMIT=1, поэтому 72.28 s включает очередь. Не заявляется ускорение или гарантированная latency; первый более простой batch-пилот занимал 24.15 s.

В последние метрики попало до 0.991838208 GB памяти при лимите 1 GB; запаса практически нет. После Git RAM/cache остаётся выделенной: 0.910966784 GB в последней выборке, CPU 0. Это не serverless-ноль в простое. DISK current 0.558596096 GB, peak 0.845832192 GB; подтверждённые disposable clones удалялись отдельно, журнал сохранялся. Пиковая память/диск требуют запаса и очистки до постоянного режима. Метрики — retry-pilot-resource-metrics.json. Дополнительная подписка не оформлялась, точный инкрементальный счёт n8n из общего bill не выделен.

## Подготовлено, но ещё не проверено/не принято

1. Постоянное ChatGPT OAuth-подключение. В браузере подготовлен Automations n8n, штатные DCR endpoints обнаружены, выбраны только workflow:read, workflow:execute, execution:read. Риск-acknowledgement, Create и OAuth consent не подтверждены. Скриншот evidence/oauth-prepared-20261106.jpg. Нужна разовая авторизация владельца. Диагностический personal MCP API key не выдаётся за установленное подключение ChatGPT.
2. Независимый новый обычный Work из Android и silent OAuth refresh после истечения access token. Текущий Work выполнялся облачно, телефон не участвовал в переносе bytes; это не независимая проверка нового Work/Android-сессии.
3. Универсальные repository/branch/destination. App установлен на все repositories владельца, однако работающий пилот намеренно ограничен private freelance/test-веткой и собственным prefix. Универсальный production-протокол ещё не реализован.
4. Автоматическое восстановление до push/при commit, не достигшем GitHub. Записанный commit сейчас проверяется на remote; если его там нет, поток останавливается, а не создаёт новый commit. Сбой между commit и записью SHA даёт uncertain и требует восстановления по локальному Git/маркеру. Это безопасная остановка, не полная автоматическая crash recovery.
5. Транзакции журнала проверены конкурентно локально, но live n8n намеренно serial=1; полноценные конкурентные разные загрузки, конфликты другого writer и рост очереди требуют отдельного испытания.
6. Отказы сейчас стандартный HTTP 500. Нужны структурированные 401/403/409/422/503 и status/result endpoint, без утечки grant в diagnostic error. Проверенный helper сам выдаёт JSON error, а не печатает credential/полную команду.
7. Пилот ещё не принимает запятые в путях; нужно заменить stock Git Add comma-list подходящим штатным Git CLI pathspec. Нужны проверки symlink ancestors до mkdir, фактического размера и Git attributes/filters до commit. Не использовать экспорт для произвольного недоверенного дерева до доработки.
8. Разрешение сейчас указывает более ранний granted-upload endpoint; fresh-token endpoint проверялся явным выбором точного адреса в клиенте. Перед production нужен один канонический endpoint, без ручной подмены.
9. После restart persistent volume сохраняет n8n DB, encrypted credentials и журнал; удалённый confirmed clone восстанавливать не нужно для replay. Потеря volume, backup/restore, pruner binary/execution data, постоянный uptime или Railway sleep/wake не приняты. Не продлевать пилот автоматически.

## Первичные источники и проверенная версия

- https://docs.n8n.io/connect/connect-to-n8n-mcp-server
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.git/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
- https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/cli/src/modules/data-table/data-table.service.ts
- https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/cli/src/modules/mcp/tools/execute-workflow.tool.ts
- https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/cli/src/modules/mcp/mcp-scopes.ts
- https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/nodes-base/nodes/Git/Git.node.ts
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app

Экспорты содержат только credential references/expressions, без секретных значений. Проверенная версия n8n 2.46.6; более новые возможности документации не считаются проверенными в этом image.
