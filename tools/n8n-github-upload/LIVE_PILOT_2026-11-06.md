# Реальный пилот Work → n8n на Railway

06.11.2026, завершение проверок около 14:12 МСК; вычисления остановлены около 14:18 МСК. Это проверка транспорта, а не полная приёмка Work → n8n → GitHub.

## Выполнено

По подтверждению владельца (дополнительный бюджет до $1, максимум два часа compute) созданы отдельные приватный Railway project `n8n-github-upload`, environment `pilot`, один service `n8n-upload`, volume 1024 MB `/data`. Точные ID и исходный абсолютный срок остановки: `railway-pilot-target.json`.

Создан отдельный приватный GitHub repository https://github.com/markmalina/automations , issue #1, ветка `infra/work-github-upload`, draft PR #2. Материалы перенесены из `freelance/tools/n8n-github-upload`, история и прежние issue #8/PR #9 сохранены; #7/Dreame не менялись.

Источник — официальный image `docker.n8n.io/n8nio/n8n:2.46.6`. Runtime подтвердил n8n 2.46.6, Git 2.55.0, UID 1000 и запись на постоянный диск. Проверка digest из Work упёрлась в ответ Docker registry 429; digest не получен, поэтому закрепление здесь по version tag, а не content digest.

Стартовая программа `pilot-bootstrap.cjs` настраивает только готовый n8n: исправляет владельца директорий, запускает локальную инициализацию, создаёт пилотного владельца, импортирует штатные credentials/workflow через n8n CLI и публикует его. Это не собственная реализация HTTP/Git загрузчика. Runtime получает программу через переменную среды; Base64 применён программно к конфигурации, не к содержимому файлов через модель.

Ключ шифрования, пароль пилотного владельца и HeaderAuth token генерировались программно без вывода в переписку и находятся в service variables. Локальные служебные файлы с ними исключены из Git. В export есть только credential references. Первичная инициализация выполняется на loopback до внешнего bind.

HTTPS domain: `https://n8n-upload-pilot.up.railway.app`. Для Railway явно выставлен `PORT=5678`, healthcheck `/healthz`. До исправления порта были неуспешные deployments; успешный — `104146b7-b9d2-415c-981e-3f0c2f34ae67`; проверенный redeploy — `3bc58a91-4bd9-4c57-a872-ba6725379afc`. После завершения пилота оба имеют статус REMOVED: активного контейнера нет, диск/настройки/домен сохранены. Endpoint сейчас не обслуживает загрузки.

## Проверено из текущего обычного Work

Использовались команды и прямые исходящие HTTPS-запросы из среды, где лежали файлы. Сами байты не печатались и не включались в аргументы модели. n8n получал HTTP body/multipart; ZIP-комплект и Dropbox не использовались.

| Проверка | Результат | Полное время запроса |
|---|---|---:|
| Raw binary 4096 bytes | HTTP 200, совпали байты и SHA-256 | 6.720677 s |
| Настоящий PNG 3,151,219 bytes, до restart | HTTP 200, совпали байты и SHA-256 | 6.952353 s |
| Тот же PNG после завершённого restart | HTTP 200, тот же SHA-256 | 6.579892 s |
| Без HeaderAuth / неправильный token | 403 / 403 до и после завершённого restart | См. JSON |
| 100 смешанных файлов, ровно 30,000,000 bytes | Один multipart request, HTTP 200, все 100 серверных SHA-256 совпали с исходными, пути из manifest соответствуют файлам | 11.472259 s |

PNG SHA-256: `93950c83617d21b8d9f945d90d3f20dc18e75ab3e6c4b3ea3dfeafb5d8fd3800`.

В mixed fixture: JPG, PNG, SVG, PDF, DOCX, TXT, JS, CSV, JSON, BIN; три уровня относительного пути, кириллица и пробелы в именах и каталогах. Это синтетические тестовые файлы, не пользовательские баннеры. Состав воспроизводится `make_transport_fixture.py`; поля multipart `f000..f099` однозначно связаны с путями/размерами/хешами в manifest. Сохранение этих путей в дереве Git ещё не проверено.

Сервер использовал Webhook → Code (только manifest/ссылки на binary) → стандартный Crypto SHA-256 для каждого файла → JSON receipt. Все bytes хешировались внутри n8n. Workflow export: `multipart-probe.workflow.json`; сопоставление каждого из 100 путей и хешей — `live-multipart-100-files.json`.

Частичные измерения фаз multipart:

- HTTP body 30,034,728 bytes, включая multipart metadata.
- `client_body_send_seconds=0.405488`: время вызова socket sendall в клиенте. Это НЕ подтверждённое время поступления всего тела в n8n; сеть/прокси могут буферизовать.
- `processingMs=581`: время процесса после разбора multipart до готовности receipt; не включает серверный разбор входного HTTP тела.
- Ожидание после sendall до response headers: 3.391039 s; включает сеть/прокси/планирование/обработку.
- Полный запрос до прочитанной проверенной квитанции: 11.472259 s.
- Git push отсутствовал. Его время и полное время Work → подтверждённый GitHub push пока неизвестны. Ускорение полного маршрута не обещается.

При проверке, начавшейся во время переключения контейнера, запрос без token получил 502; позднейшие запросы прошли. Этот переходный результат не удалён: `live-probe-after-restart.json`. Стабильный повтор после готовности: `live-probe-after-restart-stable.json`. Это single-instance deployment с возможным перерывом при restart, не zero-downtime HA.

## Ресурсы и остановка

Последние samples перед остановкой: RAM 0.493490176 GB, CPU_USAGE 0.0057002333, disk 0.131637248 GB. Максимум RAM в окне с запуском/тестом — 0.624410624 GB. Метрики в `railway-pilot-metrics.json` содержат также средние за час с нулевыми samples до создания: их нельзя выдавать за среднее idle n8n.

При неизменной RAM около 0.5 GB и работе 24/7 арифметический ориентир платы только за RAM — около $5/месяц по ставке $10/GB-month; дополнительно CPU, disk и сеть. Это не месячный замер и не зафиксированная цена. Sleep-on-idle не включён и не проверен. Один экземпляр может обслуживать несколько процессов без отдельного контейнера на каждый.

Compute остановлен через Railway UI: Deployment actions → Remove у успешного тестового deployment. Service/volume/variables/domain не удалялись. MCP readback подтвердил отсутствие SUCCESS/DEPLOYING deployments; UI показывает `Service is offline`. Screenshot `evidence/railway-pilot-stopped-2026-11-06.jpg` показывает offline и оставшиеся исторические FAILED, которые не означают, что успешных тестов не было.

Постоянный диск остаётся тарифицируемым по использованному месту. Точный дополнительный bill пилота ещё не отделён в billing; не выдаём оценку за оплаченный счёт. Для следующего старта применять текущую конфигурацию через новый deploy/redeploy; фиксированный PILOT_DEADLINE_MS не продлевается автоматически и после его истечения процесс сразу завершается.

## Диск и восстановление

`/data/.n8n` — SQLite, настройки и credentials; `/data/work` — разрешённая область файловых nodes. `/data/work/git`, `/data/work/uploads`, `/data/work/receipts` подготовлены для будущих Git copies, staging и квитанций. Реальной GitHub working copy пока нет.

Проверенный redeploy сохранил workflow, credential и ключи на том же volume: последующий authenticated PNG test прошёл. Для потери volume нужен отдельный backup/restore, не проверенный этим restart. Клоны Git можно восстанавливать из GitHub, но база credentials и квитанции требуют backup и того же encryption key. Срок хранения/очистка binary execution files перед постоянной эксплуатацией ещё требуют настройки: рост disk виден по samples.

## Что ещё не выполнено

Нет доступа Git из n8n к приватному GitHub, commit/push, GitHub download/hash acceptance, обновления существующих файлов, атомарной защиты от смешивания/дубликатов и восстановления после обрыва на границе push. Нет полноценного workflow загрузки. MCP/OAuth grant для последующих Work и срок обновления сессий не настроены. Отдельный новый Work, управляемый из Android, не проверен: текущий тест подтверждает только текущий обычный Work.

Предлагаемый следующий способ доступа к GitHub: отдельный private GitHub App `markmalina-n8n-upload`, Contents read/write и обязательный Metadata read, установка сначала только на `markmalina/freelance`. Остальные repository/account/organization permissions — No access. Короткий installation token автоматически выпускается приложением (GitHub срок 1 час), а не переподключением пользователя для каждого push. Приложение/ключи/установка ещё НЕ созданы. Форма подготовлена до Create; выдача нового доступа вынесена владельцу на подтверждение.

Источники: https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app ; https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app .
