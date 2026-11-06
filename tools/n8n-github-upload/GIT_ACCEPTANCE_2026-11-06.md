# Реальная проверка Work → n8n → GitHub

06.11.2026. Это завершённая итерация приёмки Git-транспорта в ограниченном пилоте, не готовый постоянный production-маршрут.

## Проверенный результат

Private repository `markmalina/freelance`, отдельная ветка `test/n8n-upload-20261106`, исходный SHA `67ea0e533dbf9d07a80ab2423b11b6cf58ee9133`. Main и баннеры Dreame не изменялись. Тестовые файлы синтетические.

| Проверка | Commit | Файлы / bytes | До подтверждения remote SHA | Скачивание и сверка |
|---|---|---|---:|---:|
| Один настоящий PNG | `cf5de102ed5a628d992f96fd4c114c064ab0cd55` | 1 / 3,151,219 | 15.178046 s | 7.539019 s, 1/1 hash совпал |
| Смешанный комплект | `6cb9e34b0eb72a1afc6f657a42881af1c5dff1f4` | 100 / 30,000,000 | 24.150163 s | 14.588334 s, 100/100 hash совпали |
| Обновление существующего BIN | `9f22ef7013e288c26449cd59cd1fbf8e24b0a330` | 1 / 155,437 | 10.059180 s | 5.381451 s, 1/1 hash совпал |

Ссылки:

- https://github.com/markmalina/freelance/commit/cf5de102ed5a628d992f96fd4c114c064ab0cd55
- https://github.com/markmalina/freelance/commit/6cb9e34b0eb72a1afc6f657a42881af1c5dff1f4
- https://github.com/markmalina/freelance/commit/9f22ef7013e288c26449cd59cd1fbf8e24b0a330

Первый commit имеет ровно одного родителя — исходный SHA и один added PNG. Второй — ровно один parent (первый commit) и 100 added files. Третий — parent второго commit, один modified file и никаких других changed paths. Эти свойства проверены независимо через GitHub connector; hashes рассчитаны по реальным скачанным байтам, а не по Git blob SHA.

## Способ передачи и Git

Файлы находились в текущем обычном Work. Клиент программно отправил один multipart/form-data запрос на комплект: JSON manifest + отдельные binary file parts. ZIP-комплект отсутствовал. Содержимое файлов не печаталось и не передавалось моделью в строках Base64. Внутренние программные преобразования конфигурации/credentials допустимы и использовались.

Приём выполняли штатные n8n nodes: Webhook HeaderAuth → Code проверки manifest/ссылок на binary → Git Clone/Switch/AddConfig → Crypto SHA-256 → Read/Write Files → Git Add → **один Commit** → Git Log → **один Push** → HTTP Request remote ref → проверенная JSON-квитанция. В nominal path ровно один Commit node и один Push node, каждый получает один item, автоматические retries не включены. В исходнике Git node подтверждён один вызов git.push. Отдельный metadata-read GitHub подтвердил один результирующий commit на комплект. Удалений не было.

Штатный Crypto удаляет binary из своего output после hash; ссылки на исходные binary восстановлены перед записью. Первоначальный тест выявил это до commit и был исправлен.

Штатный Read/Write Files не создаёт родительские директории: `openWithoutFollowingSymlinkedAncestors` вызывает `pinDirectory(...,{create:false})`. Для mkdir использован готовый Execute Command с единственной командой `mkdir -p --` и shell-quoted путями из проверенного manifest. Для этого в этом собственном instance включён стандартный Execute Command; localFileTrigger остаётся исключён. HTTP-клиент не передаёт команды shell. Собственный binary/Git uploader не написан.

После подтверждённого push отдельный защищённый workflow использовал HTTP Request, чтобы скачать **каждый файл из точного commit SHA**, и стандартный Crypto SHA-256. Хеши сопоставлены с исходными файлами Work. Первичный upload receipt и 100 строк результатов сохранены в `git-probe-100-files-receipt.json` / `git-probe-100-files-receipt-verified.json`.

## Имена и структура

В комплекте JPG, PNG, SVG, PDF, DOCX, TXT, JS, CSV, JSON, BIN. Сохранились относительные пути вида `Раздел 1/вложенная папка/Файл 001.jpg`, кириллица, пробелы и байты каждого файла. Тестовое назначение — `n8n-tests/1046ee79-090f-40ac-8348-2dc4c19a72fa/`. Изменённый существующий файл — `Раздел 5/вложенная папка/Файл 100.bin` внутри этого назначения.

Это тестовая фиксированная ветка/репозиторий, а не уже реализованный интерфейс произвольного repository/branch/destination.

## Раздельные измерения

Для комплекта 100/30 MB:

- Client socket sendall HTTP body: **0.373754 s**. Это локальный интервал отправки в сокет, не подтверждённое время приёма последнего байта n8n: сеть/прокси могут буферизовать.
- Обработка после разбора multipart до готовой квитанции: **17.018 s**, включая clone/hash/write/commit/push/ref-check.
- Интервал вокруг стандартного Git Push node: **3.452 s**, включая его scheduling/выполнение, без последующего remote-ref read.
- Прочая серверная часть по разности: **13.566 s**.
- Полное время Work до прочитанной квитанции с подтверждённым SHA: **24.150163 s**.
- Отдельная последующая проверка скачиванием всех 100 файлов: **14.588334 s**.

Это реальные замеры данного пилота; baseline прежнего маршрута не измерен, коэффициент ускорения не заявляется. HTTP ingress/parser time отдельно не измерен.

## Авторизация

Владелец вручную применил GH_APP_PRIVATE_KEY; deployment `9ea8de8f-f6d1-4f6b-ae03-cd49f3096397` был SUCCESS. Runtime проверил RSA PEM, подписал JWT и получил от GitHub подтверждение App ID 5641721 / slug markmalina-n8n-upload. Public fingerprint: `XipowE+pnfV3eLf1INPSHPHGfsDstKWwpUxOvRJ3wXg=`.

GitHub App installation 179245428 по отдельному подтверждению владельца имеет All repositories. Но **пилотный installation token был выпущен только для repository ID 1378687935 (freelance)**, contents write. Private key, JWT и installation token не выводились и не сохранялись в Git. Credentials импортировались штатным CLI n8n в зашифрованную базу; временный файл удалялся. Export содержит только credential references.

Для пилота token выпускается при старте и имеет срок GitHub один час. Автоматическое продление во время постоянной работы ещё не реализовано. Это не финальная настройка аутентификации production.

## Рабочие копии и ресурсы

Один volume 1 GB `/data`: SQLite/settings/credentials в `/data/.n8n`, рабочие копии `/data/work/git/pilot-<uploadId>`, staging/binary storage n8n на том же диске, служебные результаты `/data/work/receipts`.

Рабочая копия 100-файлового теста: `/data/work/git/pilot-1046ee79-090f-40ac-8348-2dc4c19a72fa`. Обновление использовало именно её. После restart volume сохраняет копии/credentials/workflows. При потере клона он восстанавливается из GitHub; credentials и квитанции требуют backup/постоянного encryption key. Полное disaster recovery не проверено.

Freelance по GitHub metadata занимает около 110 MB. Полный clone для каждой попытки даёт заметный disk/cache overhead. Неуспешная изолированная копия `bb3b9290-353c-43c8-bd3d-4187814c76d2` была удалена операторским bootstrap helper: только заранее известный disposable clone, без изменений удалённого репозитория. Серийная очистка/retention ещё не готовы.

В наблюдаемом окне максимум MEMORY_USAGE_GB — **0.97959936**, disk к завершению — около **0.743399424 GB**. Это включает startup/Git/cache, не устойчивая idle RAM. Средние за час содержат нули периода остановки. Новых Postgres/Redis/LLM/Railway Agent не добавлялось.

Абсолютный таймер пилота — 15:45:16 МСК, без автоматического продления. В логах подтверждены PILOT_DEADLINE_REACHED, SIGTERM, остановка scheduler/n8n. Проверка в 15:47 дала replicaStatus.running=0; deployment metadata ещё SUCCESS/state online, что не равно работающей replica. Healthcheck из Work перестал отвечать (timeout). Последний RAM sample может быть историческим, он не используется как доказательство работающего процесса. Сохранённый диск остаётся платным. Точный дополнительный billing пилота отдельно не измерен.

## Матрица приёмки и остаток

| Требование | Состояние |
|---|---|
| Обычный Work → n8n → приватный GitHub, один binary, совпадение SHA-256 | PASS |
| 100 отдельных смешанных файлов / 30 MB, все байты и пути | PASS |
| Один commit и один Git push на комплект | PASS nominal path; граф/source + remote history |
| Кириллица, пробелы, вложенные папки, ZIP не требуется | PASS |
| Обновление существующего файла без изменения посторонних | PASS, GitHub diff ровно один modified path + download hash |
| Несколько одновременных загрузок | Отдельные clone paths и concurrency=1 настроены; concurrent/crash тесты не выполнены |
| Повтор после сетевого обрыва возвращает прежний commit | НЕ ГОТОВО: нет durable idempotency journal и recovery после push |
| Restart | Transport/credentials ранее проверены; Git workflows переживали redeploy, но целая batch-Git приёмка после финального restart не повторена |
| Следующий новый Work без ручной передачи секрета | НЕ ГОТОВО: постоянный OAuth/MCP grant ещё не настроен |
| Android | Выполнено из текущего обычного Work, управляемого пользователем; отдельный новый Android Work не проверен |

Текущий workflow намеренно помечен productionReady=false. Повтор того же uploadId не имеет корректной ветки получения старой квитанции; не использовать в роли готового массового загрузчика. Нужны атомарный журнал/проверка marker после неизвестного push, безопасная очистка, постоянный refresh/manifest-bound grants, произвольные разрешённые назначения и окончательная сквозная приёмка. Наличие All repositories в GitHub App не закрывает эти требования.

Разработка и доказательства: automations #1 / draft PR #2. Текущий прежний способ загрузки остаётся рабочим до полной приёмки нового.
