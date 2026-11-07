# S2.B / №12 — приватный read-only readback VERIFIED

07.11.2026, 14:22 МСК. Готово к приёмке контроллером.
Задача: https://github.com/markmalina/automations/issues/12
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Принятие S2.A:
https://github.com/markmalina/automations/issues/10#issuecomment-6706116436

## Результат

**VERIFIED, fileCount=1, verifiedFiles=1, terminal exit0.**
Проверен только уже существующий README.md небольшого приватного служебного
репозитория. Это настоящее read-only свидетельство GitHub connector, без fake
transport. Bundle/receipt явно **синтетические** для чтения существующего файла,
а не квитанция n8n. Никакой загрузки или новой записи в target не было.

## Source и baseline

Automations main до отчёта:
4f072366f471c0d4e82e1768dadde5742e185b9f.
Прочитаны №12 полностью, свежие комментарии, WORK-RULES, WORK_CLIENT,
hashes/границы отчёта и принятие S2.A/R1. До принятия №12 была без комментариев
и другого claim. В актуальном дереве нет AGENTS.md/WORK-PARENT.json.
Предыдущие проверки R1/S2.A и зелёные CI не повторялись.

Использованы без изменений три файла из одного принятого source:
e605fd9881abd33b4630998146ab25571a2e05a3 (merge PR11).
Exact source прочитан через GitHub; локальные SHA-256 сверены с принятым отчётом:

| Файл | SHA-256 |
| --- | --- |
| work_upload.py | bd18630daef9ca5f4e925dd1ccf8474e8696bff6f692afaec7fc9b978439c515 |
| work_readback.py | 931d3f88e40130fff40a7925111cc84c2e811fd80327ed349f285fb2b5d6aa95 |
| WORK_READBACK_BRIDGE.js | 72d7b720f604cf4c500863b564aa2fe5366f7f53c3b7ad6d800098c5c9fb19bd |

## Выбранный target и фактические bytes

GitHub get_repo подтвердил owner markmalina / ownerId23397294,
repositoryId1331657982, visibility=private и default_branch=main.
Это metadata-свидетельство отделялось от последующей проверки bytes.

Default branch закреплена до чтения, дальнейшая проверка шла по exact commit,
без повторного чтения branch tip:

| Поле | Подтверждённое значение |
| --- | --- |
| Repository | markmalina/ops |
| Visibility | private |
| Exact commit | e2b0a2851fb15fd204a43d6951859dcfa0f0965e |
| Root tree | 11036409d845563ba886bb69ea57410a563111f4 |
| Path | README.md |
| Type / mode | blob / 100644 |
| Bytes | 4958 |
| SHA-256 | 31c756cf4f498080f3db7b1f86888d9eddf88d0337e14adbf17fa5ebf3fb3c6b |
| Git blob SHA | e1fe91e5ea734664b5e056971504348ac8c58f3b |

Exact commit:
https://github.com/markmalina/ops/commit/e2b0a2851fb15fd204a43d6951859dcfa0f0965e

Корневой tree подтвердил README как обычный служебный файл до256KiB.
Другие файлы ops не читались; .env/secrets/keys/tokens/credentials/БД/личные
payload не выбирались. Содержимое README, его строки и синтетический receipt
в этом отчёте отсутствуют.

## Как получено свидетельство

1. Первый github_fetch_file(repository_full_name=markmalina/ops,
   path=README.md, ref=exact commit, encoding=base64) действительно вернул bytes.
   Они программно переданы в подготовитель через защищённый stdin после
   READY_FOR_GRANT; не через модель, stdout, shell command, argv или Git.
2. В собственной временной папке0700 создана только копия выбранного файла0600.
   Размер и Git blob SHA первого read проверены, SHA256 вычислен из bytes.
   Существующий prepare создал synthetic bundle/receipt0600 для этого файла.
   Это не выдача grant и не n8n execution.
3. Неизменённый WORK_READBACK_BRIDGE.js вызвал принятый verifier через настоящий
   exec_command/write_stdin. Независимый второй read прошёл четыре фазы:
   github_fetch repository → github_fetch exact Git commit →
   github_fetch root tree → github_fetch_file exact-ref base64 bytes.
   Все четыре connector calls успешны. Observer сохранил только тип/фазу и
   isError=false, без provider body или private content; source не менялся.
4. Сам verifier подтвердил repositoryId/full_name/owner, exact commit/tree/path,
   фактический размер и SHA256 manifest, пересчитанный Git blob SHA. Он вернул
   work-readback/v1: VERIFIED /1/1 и URL указанного exact commit.
   Driver наблюдал terminal exit0. Metadata-доступ не использован вместо bytes.
5. Локальное чтение безопасного report подтвердило VERIFIED1/1; права source,
   bundle, receipt и result были0600. После сохранения безопасных metadata все
   четыре собственных временных файла и подготовитель удалены, временная папка
   отсутствует. Приватные bytes также убраны из orchestration store.
   Исходники/файл в ops не менялись.

## Границы принятия

VERIFIED относится только к этому одному4958-byte README и существующему
GitHub-подключению в данном Work. Размеры connector response до32MB,100/30,
другие private repositories и настоящий private n8n upload не проверялись.

S1/№9 остаётся BLOCKED; полный S2 и S3–S6 не завершены. Railway/permissions/
pending/volume/SQLite/server candidate не читались и не менялись.
Нет n8n grant/upload/replay, Deploy/restart, новых credentials/HTTP обхода,
записей в ops или новых GitHub fixtures. Verifier/bridge/uploader не изменены.
Другие репозитории не исследовались. Единственная планируемая запись —
этот отчёт в automations и ссылка/свидетельство в №12.

Новых hosted CI/jobs/таймеров не было: source не менялся. Локальные процессы
завершены. №12 остаётся открытой; приёмку подтверждает контроллер, её
автоматическая доставка между Work не заявляется.

ДАЛЬШЕ: контроллер — проверить это свидетельство S2.B и принять №12 либо вернуть замечания.
