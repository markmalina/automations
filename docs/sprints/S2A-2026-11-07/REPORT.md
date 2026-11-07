# S2.A / №10 — exact-commit readback, готово к приёмке

Дата подготовки: 07.11.2026, 13:50 МСК; обновление R1 — 14:08 МСК.  
Задача: https://github.com/markmalina/automations/issues/10  
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md  
Передача: https://github.com/markmalina/automations/blob/ad155965a73b4f4e768d7323112c46f32127ebf3/docs/handoffs/S2A-WORK-READBACK-2026-11-07.md

## Результат и границы

Существующий work_upload.py проверял receipt, но не скачивал удалённые bytes.
Добавлены один Python verifier и его конкретный code-mode driver через прежнее
GitHub-подключение. WORK_CLIENT.md теперь описывает общий prepare → OAuth grant →
защищённый receive-grant → upload → независимый readback → cleanup.

Это независимая подготовка S2.A. Реальные grant/upload/replay n8n не вызывались.
S1 / №9 остаётся BLOCKED. Спринты S2 целиком и S3–S6 не выполнены.
PR не объединяется, №10 остаётся открытой до решения контроллера.

## A0 — baseline и небольшой diff

Base main: ad155965a73b4f4e768d7323112c46f32127ebf3,
tree a497acf9e9c58a4b8ff6711c054544afab994f74.
Ветка: feat/work-exact-readback-10. №10 до принятия не имела комментариев;
открыты были только старые draft PR2–5. Другого свежего claim/PR результата
не найдено. Это не телеметрия остальных чатов.

Прочитаны №10, её комментарии, передача, актуальный регламент, README,
work_upload.py, test_work_upload.py, WORK_CLIENT.md, UNIVERSAL_ROUTE.md,
существующий CI и границы REPORT/candidate S1. В актуальном дереве source
AGENTS.md/WORK-PARENT.json отсутствуют; чужие рабочие каталоги не используются.

Изменяются ровно четыре client-side файла и этот отчёт:
- work_readback.py — verifier, без HTTP uploader/auth/server.
- WORK_READBACK_BRIDGE.js — исполняемый code-mode driver прежнего GitHub connector.
- test_work_readback.py — позитивные/негативные локальные сценарии.
- WORK_CLIENT.md — короткая воспроизводимая последовательность для нового Work.
- docs/sprints/S2A-2026-11-07/REPORT.md — свидетельства и границы.

work_upload.py не изменён; его prepare/bundle_valid/receipt_valid и secure stdin
переиспользуются. Существующий test_*.py discovery уже подхватывает новый тест;
CI workflow менять не требуется.

## A1 — что именно проверяет verifier

Входы: сохранённые bundle и receipt; повторная полная проверка их binding
существующим клиентом до первого connector request. commitSha берётся только
из связанной квитанции и не меняется в течение проверки.

Driver вызывает доступные реальные интерфейсы:
1. github_fetch /repos/{repository}: точные repositoryId/full_name/ownerId/login.
2. github_fetch /repos/{repository}/git/commits/{exactSha}: тот же commit SHA и root tree.
3. github_fetch /repos/{repository}/git/trees/{treeSha}: нерекурсивные tree entries,
   последовательный обход точного prefix/path с cache, truncated=false.
4. github_fetch_file(repository_full_name, path, ref=exactSha, encoding=base64):
   реальные bytes каждого файла из того же immutable commit.

Этот GitHub connector действительно возвращает structuredContent
{content,encoding,sha,...} в base64-режиме, в том числе для JPG. Generic contents
и fetch_blob здесь возвращали декодированный текст; они не используются как
доказательство бинарных bytes. Возвращённые display_url/download_url и ссылки
provider JSON не используются для сетевых запросов. Нового token нет.

Bytes поступают из connector tool result в программную переменную functions.exec,
затем одной ограниченной JSON-строкой через write_stdin после echo-off handshake.
Driver не печатает provider responses и не вставляет их в shell/argv/Git. Helper
декодирует внутренний GitHub Base64 в памяти, сверяет размер и SHA-256 с manifest,
пересчитывает Git blob SHA из реальных bytes и сравнивает с exact tree entry.
Поддерживаются prefix, Unicode/NFC, пробелы, проценты, пустые и бинарные файлы.
Symlinks/submodules/неожиданный mode отклоняются: существующий uploader создаёт
только mode100644.

Report0600: VERIFIED / MISMATCH / UNAVAILABLE, fileCount/verifiedFiles и
самостоятельно построенный URL exact commit, безопасный errorCode. Произвольный
provider body, URLs, headers, payload и credentials в отчёт не попадают.
Exit codes 0/1/2. UNAVAILABLE не является PASS, повторного upload/нового UUID нет.

Ограничения: входные bundle/receipt — обычные файлы до1MiB, symlink/FIFO
отклоняются неблокирующим opener существующего клиента. Прежний manifest limit
100 файлов /32,000,000bytes; до1000 connector requests, общий budget120с,
response budget20с, максимум44,000,000UTF8bytes одной stdin-строки. Tree cache
ограничен числом запросов, отдельное дерево — до100000 entries и bounded line.
Нет автоматических retries или чтения mutable branch tip. Внешний tool call
может завершиться позже локального timeout; поздний ответ не принимается за PASS.
Если connector не отдаёт полные bytes/metadata — UNAVAILABLE, без расширения
permissions или смены транспорта по догадке.

## A2 — локальные проверки и self-review

Финальная локальная версия: Python3.12.14, Node24.22.1.
- python -m unittest -v test_work_readback.py: **24 PASS** (20 исходных +4 R1).
- python -m unittest discover -s tools/n8n-github-upload -p 'test_*.py' -q:
  **64 PASS** (40 прежних +24 readback), 0 fail.
- python -m py_compile work_readback.py и node --check WORK_READBACK_BRIDGE.js:
  PASS.
- Реальные локальные pipe и PTY прогнаны против fake transport. Echo-off handshake
  проверен до передачи canary, terminal modes восстановлены, canary отсутствует
  в captured stdout/stderr/PTY, report имеет mode0600.
- Проверены zero/binary/Unicode/prefix/percent, corrupt bytes/size/Git blob,
  отсутствующий путь, неверные repo/owner/commit/tree, движение branch tip при
  неизменном exact ref, symlink/submodule/mode, truncated/duplicate tree,
  invalid Base64/encoding/oversize, malformed receipt/bundle до обращения,
  redirect/access/timeout/EOF/sequence и глобальный timeout.
- Self-review нашёл возможность блокировки на FIFO до connector deadline:
  входные JSON переведены на существующий safe ordinary-file opener, добавлены
  две проверки. Также driver проверяет UTF8 byte budget и terminal exit helper.
  Это собственный разбор, не независимое review.


### Исправление R1 после проверки контроллера

Замечание:
https://github.com/markmalina/automations/pull/11#issuecomment-6705972062 .
Контроллер воспроизвёл ложный timeout test harness на прежнем head
8098cfcfe131d4f43bd1f469f429bd78eecfda76. Причина — select перед readline
буферизованного stdout: REQUEST уже находился в Python-буфере после чтения
READY, хотя OS fd больше не был readable. Это не установленный сбой verifier.

В test_work_readback.py добавлен только тестовый DeadlineLines:
os.read читает OS descriptor, явный byte buffer сначала отдаёт готовые строки,
select ждёт только при отсутствии полного newline. Частичная строка сохраняется,
remaining считается от одного deadline на всю строку и не сбрасывается при
поступлении очередного фрагмента. Сохраняется прежний 3s deadline; buffer
ограничен65536bytes, EOF без newline отклоняется. Popen stdin/буферизация не
менялись; stdout Python reader больше не используется для чтения.

Четыре детерминированные regression:
- READY и REQUEST записаны одним os.write в реальный pipe, writer остаётся
  открытым. После первой строки OS fd пуст; вторая возвращается из явного
  буфера без второго select.
- Prefix частичной строки записан до чтения; tail + следующая строка
  выпускаются только на втором вызове wait. Проверяется целая строка,
  сохранение остатка и remaining3s→2s от исходного deadline.
- Неоконченный prefix не обновляет deadline: remaining3s→0.5s, затем отказ.
- EOF после prefix не принимается за полную protocol line.

Контроль регрессии: подстановка прежнего алгоритма select + buffered readline
в новый coalesced regression детерминированно даёт ожидаемый FAIL
«select called despite an already buffered complete line». С исправленным
reader все24 readback теста и полный64-test discovery PASS. Sleep/retry,
увеличение timeout или ослабление canary/no-echo/termios/cleanup не добавлялись.
Реальные pipe/PTY тесты продолжают проверять защитные свойства и report0600.

В исправлении меняются только этот тестовый файл и отчёт. Product verifier,
code-mode bridge, WORK_CLIENT.md, work_upload.py и все S1/server blobs неизменны.
Отдельный публичный smoke не повторялся: исполняемые product bytes не менялись.
Исторический CI42365732052 остаётся доказательством только прежнего head;
один необходимый новый CI для R1 фиксируется после завершения в №10.

Новый hosted CI должен быть ровно один на подготовленном PR head. Его actual
run/status публикуется в итоговом комментарии №10 после чтения terminal result;
этот source-отчёт заранее не утверждает успех CI. Зелёный CI PR8 не перезапускался.
Hosted CI не является end-to-end n8n приёмкой.

## Отдельное реальное read-only свидетельство

Финальный helper/driver проверены реальными exec_command/write_stdin и прежними
GitHub tools, без прямого сетевого обхода и без публикации тестовых файлов.

Exact source commit: ad155965a73b4f4e768d7323112c46f32127ebf3.
Репозиторий markmalina/automations, repositoryId1448151721.
Bundle/receipt для этого smoke **синтетические**, созданы для двух уже существующих
публичных файлов; это не новая операция upload и не настоящая квитанция n8n.
Ожидаемые manifest bytes сначала получены отдельно, затем verifier независимо
прошёл repo/commit/tree/path и повторное скачивание через закреплённый ref.

| Путь | Bytes | SHA-256 | Git blob SHA |
| --- | ---: | --- | --- |
| README.md | 98 | 8efc2f20cd890abda15a48c24dfe9cc457bc1ffc0960a59eba79bfea1dbd44f8 | 1ecbe76d3bbf2b30a7f792617a2cd85e2b39716c |
| docs/evidence/automations-public-20261107.jpg | 89482 | 7bfa639fc1670dfb467e2f79392e7d4e402aca93d2d97ddb75fa7f324d58b5ec | 6d2bb3e64eb1e9584bb399463c9ad0d4115251ac |

Фактический report: status VERIFIED, fileCount2, verifiedFiles2,
https://github.com/markmalina/automations/commit/ad155965a73b4f4e768d7323112c46f32127ebf3 .
Финальный процесс helper наблюдался завершённым с exit0.
Fake tests не подменяют это свидетельство. Публичный smoke не доказывает доступ
к private repository, максимальному размеру connector response или настоящее
upload→readback после n8n. Эти критерии остаются PENDING. Локальные smoke payload
копии удаляются после сохранения metadata; реальные user files не удаляются.

## Закрепление версии для следующего Work

Взять exact head из итогового комментария/PR №10, а не изменяемый main.
Все перечисленные файлы — из одного head; сверить SHA-256 до исполнения:

| Файл | SHA-256 |
| --- | --- |
| work_readback.py | 931d3f88e40130fff40a7925111cc84c2e811fd80327ed349f285fb2b5d6aa95 |
| WORK_READBACK_BRIDGE.js | 72d7b720f604cf4c500863b564aa2fe5366f7f53c3b7ad6d800098c5c9fb19bd |
| test_work_readback.py | 6e73109bc351a03983228ef887d0f52d81ce238ef267f1ca3dbda3cdadab8af7 |
| WORK_CLIENT.md | b78664dae15be8c9a3b01473b74b584500c436053c7e755a5e13b9624fdff55a |
| work_upload.py | bd18630daef9ca5f4e925dd1ccf8474e8696bff6f692afaec7fc9b978439c515 |

## Неприкосновенный S1 и остаток

Не менялись pilot-bootstrap.cjs, upload-ledger.cjs, оба workflow, их генераторы,
docs/sprints/S1 candidate, текущие credentials/permission settings и Railway.
Точный server source по-прежнему закреплён source2e7643bd805840f5ddba4d9836a8caf8fc6f508d;
его runtime hashes совпадают с S1 candidate. Нет Deploy/restart/pending-patch/
volume/SQLite mutations, n8n grants/uploads/replay и изменений соседних repos.

Готовая подготовительная часть: независимый byte verifier, конкретный connector
bridge, инструкция и локальные/публичные read-only свидетельства. Остаются
приёмка контроллера и, в разрешённом будущем этапе после S1, настоящий OAuth
grant/upload/readback двух назначенных repos, обновление/replay и приватные bytes.

A3 завершается публикацией одного unmerged PR, проверкой exact head/remote bytes
и CI, затем итоговым комментарием в №10 и остановкой. Автоматическое наблюдение
или доставка между Work не заявляются.

ДАЛЬШЕ: контроллер — проверить PR и этот отчёт, принять S2.A либо вернуть замечания.
