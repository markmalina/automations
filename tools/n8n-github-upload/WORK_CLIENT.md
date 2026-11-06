# Work: подготовка и бинарная передача

`work_upload.py` — клиент на стандартной библиотеке Python. Он не создаёт
постоянные credentials, сервер, Git-клон, ZIP или Base64-пакет. Файлы идут
напрямую HTTPS multipart; через модель и MCP передаётся только метаинформация.

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
   читает exact GitHub commit через подключённый GitHub-коннектор и сверяет
   скачанные байты. HTTP200 или валидная квитанция сами по себе не заменяют
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
