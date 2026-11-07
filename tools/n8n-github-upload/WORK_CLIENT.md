# Work: подготовка и бинарная передача

`work_upload.py` — клиент на стандартной библиотеке Python. Он не создаёт
постоянные credentials, сервер, Git-клон, ZIP или Base64-пакет. Файлы идут
напрямую HTTPS multipart; в upload-вызове MCP передаётся только метаинформация.
Независимый readback получает bytes через GitHub MCP программно, без вывода в модель.

1. Work определяет назначенный репозиторий `markmalina/name`, его числовой ID,
   существующую ветку и относительный `prefix` (может быть пустым). В
   `target.json` записываются ровно `repositoryId`, `repository`, `branch`,
   `prefix`. `files.json` содержит массив `{source: абсолютный локальный путь,
   path: относительный путь внутри prefix}`.
2. Подготовить комплект:
   `python work_upload.py prepare --target target.json --files files.json --output bundle.json`.
   Результат — metadata-only bundle0600 с UUID, реальными размерами/SHA256,
   manifest, его digest и `grantRequest`. UUID сохраняется для всех повторов;
   для восстановления можно явно передать прежний `--upload-id`.
3. Через уже подключённый OAuth n8n выполнить опубликованный
   `workUploadGrantPilot` с `webhookData.body = bundle.grantRequest`.
   Выданное краткосрочное разрешение получить программно из выбранного
   конечного node execution. Для безопасного сохранения запустить
   `python work_upload.py receive-grant --bundle bundle.json --output grant.json`
   с обычным stdin pipe, если среда поддерживает открытый pipe. В текущем
   exec_command режим tty:false сразу даёт EOF и для write_stdin не подходит.
   Здесь запустить receive-grant через exec_command с tty:true. Сам helper
   через стандартный termios отключает ECHO/ECHONL/ICANON, затем печатает и
   flush-ит только READY_FOR_GRANT. Передавать вычисленную JSON-строку через
   write_stdin разрешается только после этого handshake и получения session_id.
   В finally исходные terminal modes восстанавливаются, в том числе при
   ошибке JSON/binding. Без termios защищённый режим отказывает E_SECURE_STDIN.
   Реальный exec_command/write_stdin bridge проверен только fake canary:
   значение не появилось ни в одном stdout, файл создан0600.

   Внутри orchestration держать структурированный результат execute/get_execution
   только в программной переменной. Значение не выводить в модель,
   `text()/notify()`, shell command, argv или Git. До write_stdin ограничить
   UTF8-размер всей JSON-строки с newline16КиБ; в code-mode без TextEncoder
   пригоден счётчик encodeURIComponent(line).replace(/%[a-fA-F0-9]{2}/gu,"x").length.
   В ответе write_stdin дополнительно проверить отсутствие token перед любым
   выводом; после сохранения очистить программную переменную. CLI принимает максимум16КиБ,
   проверяет UUID/digest/target/expiry/endpoint и сохраняет только необходимые
   поля в файл0600. stdout содержит только saved/UUID/expiry. Дополнительный
   постоянный секрет для нового Work не требуется.
4. Передать:
   `python work_upload.py upload --bundle bundle.json --grant grant.json --receipt receipt.json`.
   Клиент до сетевого подключения проверяет target/digest/UUID/expiry/URL и
   повторно хэширует каждый открытый файл. Endpoint допускается только
   `https://n8n-upload-pilot.up.railway.app/webhook/work-owner-repository-upload-v1`.
   TLS проверяется, redirect и автоматические повторы отключены.
   Socket/response timeout300секунд: server ограничивает частоту GitHub writes,
   поэтому100файлов могут обрабатываться около двух минут. Это не обещание
   скорости или подтверждение живого замера.
5. Полученная квитанция проверяется по repo/branch/UUID/числу/объёму/commit/
   путям/SHA256/размерам. Неизвестные поля ответа удаляются. Work отдельно
   запускает `work_readback.py` через `WORK_READBACK_BRIDGE.js`: существующий
   GitHub-коннектор возвращает bytes программно, helper сверяет их по exact commit.
   Конкретный порядок приведён ниже. HTTP200 или валидная квитанция сами по себе не заменяют
   такую живую проверку. После использования удалить временный grant-файл.

Лимиты:1–100файлов, до32,000,000байт в сумме; канонический manifest не более
30,000UTF16 code units для безопасной передачи его существующему n8n
ExecuteCommand. Полный путь prefix/path не длиннее2048UTF8байт, каждый компонент
не длиннее255байт. Источники — только обычные файлы: symlink/FIFO/device
отклоняются, открытие неблокирующее с повторной проверкой типа и inode.
Пути должны быть NFC POSIX; не допускаются traversal, `.git`,
управляющие символы/обратный слеш/запятая, коллизии регистра или файл/каталог.
`.github/workflows` возвращает E_WORKFLOWS_PERMISSION: действующему App
подтверждён только contents:write. Защита веток не отключается.

Потерянный ответ/ошибка соединения: **сохранить тот же UUID, manifest и байты**.
Получить новое краткосрочное разрешение и повторить тот же комплект. Если
server пометил commit как записанный, но он ещё не достижим из ветки, текущая
консервативная server-политика возвращает uncertain; не создавать автоматически
новый uploadId, commit или принудительный ref update. Требуется восстановление
по сохранённому журналу. Клиент не пытается обойти этот отказ.

Офлайн проверки запускаются `python -m unittest -v test_work_upload.py`.
Они используют fake HTTPS transport и реальные бинарные файлы, включая
100файлов/30МБ. Это проверка клиента, не живая приёмка n8n/GitHub или включение
постоянного сервиса.


## Независимая проверка после upload (S2.A)

Статус: source/offline и небольшой публичный read-only smoke описываются в отчёте
№10. Установка S1, настоящий n8n grant/upload и приватный readback остаются PENDING.
Этот раздел исполняет Work; Марк не готовит JSON, не переносит секреты и не запускает
команды. Для ошибки readback нельзя автоматически делать новый upload или uploadId.

1. Взять `work_upload.py`, `work_readback.py` и `WORK_READBACK_BRIDGE.js` из одного
   проверенного exact commit PR, принятого контроллером. До исполнения сверить
   SHA-256 с таблицей в отчёте №10; не скачивать изменяемый main по предположению.
2. Использовать уже сохранённые bundle0600 и receipt0600. Helper повторяет
   `bundle_valid`/`receipt_valid`, фиксирует `commitSha` из связанной квитанции,
   затем независимо читает repository ID/owner, commit, деревья по SHA и каждый
   prefix/path. Ветку и URLs квитанции/дерева/download_url для загрузки не использует.
3. В functions.exec задать `store('work-readback-config', {helper: абсолютный путь
   к work_readback.py, bundle: абсолютный путь к bundle.json, receipt: абсолютный
   путь к receipt.json, output: абсолютный путь к readback.json})`. Затем выполнить
   проверенное содержимое `WORK_READBACK_BRIDGE.js` как code-mode cell. Использовать
   exec yield 1000мс; если получен running cell ID, продолжать functions.wait.
   Bridge сам запускает helper через exec_command(tty:true). Только после
   READY_FOR_GRANT (переиспользованное имя защищённого stdin handshake) и
   READBACK_REQUEST с sequence передаёт одну JSON-строку через write_stdin.
   ECHO/ECHONL/ICANON отключены до handshake и восстановлены finally.
4. Bridge вызывает существующий GitHub OAuth connector, без нового token:
   `github_fetch` для `/repos/{repository}`, `/git/commits/{exactSha}`,
   `/git/trees/{treeSha}` (нерекурсивно, с cache в helper); `github_fetch_file`
   с `repository_full_name`, полным `path`, `ref=exactSha`, `encoding=base64`.
   Успешные ответы JSON API разбираются программно из structuredContent.content;
   file возвращает structuredContent `{sha, encoding, content}`. Обычные fetch_blob
   и generic contents могут вернуть декодированный текст; для binary bytes они
   здесь не используются. Внутренний Base64 не выводится в модель или stdout.
5. Helper декодирует bytes в памяти, сверяет размер и SHA-256 с manifest, а также
   пересчитывает Git blob SHA из bytes и сравнивает с exact tree entry. Отклоняет
   symlinks/submodules/неожиданный mode, truncated/неполные ответы. Report0600
   содержит только VERIFIED/MISMATCH/UNAVAILABLE, проверенное число файлов,
   repo/exact commit URL и безопасный errorCode. Exit: 0/1/2 соответственно.
   Provider URL/body, grants, headers и bytes в report отсутствуют.
6. Только VERIFIED означает проверенные remote bytes. UNAVAILABLE означает
   отсутствие доказательства (включая неполную выдачу bytes коннектором, отказ
   доступа или timeout), а не успех. MISMATCH требует разбора при прежнем UUID.
   Не делать повторную загрузку для исправления readback. Очистить короткий grant
   в finally независимо от исхода; сохранять прежние bundle/receipt/исходные bytes
   до разбора. Helper не создаёт копии payload и не удаляет пользовательские файлы.

Лимиты verifier: прежние 100 файлов / 32,000,000 bytes; 120с на проверку, 20с на
один stdin response, 1000 metadata/file requests, максимум44,000,000bytes JSON
строки ответа. Нет автоматических retries/redirects или HTTP-загрузки по URL.
Сбой/лимит соединения или коннектора даёт UNAVAILABLE; это не обещание, что
каждый приватный файл до32МБ коннектор сможет вернуть целиком. Provider call
может пережить локальный deadline: его поздний ответ не принимается за успех.

Локальные новые проверки: `python -m unittest -v test_work_readback.py`; входят
в существующий CI discovery `test_*.py`. Fake transport проверяет логику и
отказы; отдельный реальный public smoke в отчёте не доказывает доступ к private.
