# №13 / S1.N — native n8n 2.46.6

07.11.2026, 15:58 МСК. Проверка завершена; готово к приёмке контроллером.
Задача: https://github.com/markmalina/automations/issues/13
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md

## Результаты по отдельности

| Проверка | Вердикт | Фактическое свидетельство |
| --- | --- | --- |
| Exact import двух exports | PASS | native import:workflow, оба rc0 |
| Первичная публикация двух ID | PASS | native publish:workflow, оба rc0; локальная БД active1, versionId=activeVersionId |
| Native grant на свежей локальной БД | PASS | loopback HTTP200, target/digest/UUID и hash/expiry локального ledger совпали |
| Запрос без header | PASS: отказ | HTTP403, новой записи grant нет |
| Невалидный fileCount0 | PASS: отказ | HTTP500, число grants осталось1 |
| Полный каталог типов | UNAVAILABLE | authenticated /types/nodes.json превысил лимит локального probe16MB |
| Ранний запрос при обновлении snapshot | FAIL в первом наблюдении | сразу после readiness исполнен старый /data path; HTTP500 |
| Последующее схождение snapshot | PASS | после bounded startup/10s наблюдения publishedVersionId совпал с activeVersionId |
| Сводная метка вспомогательного N2 harness | FAIL: ошибка ожидания | harness требовал именно401; native вернул403. Этот FAIL не скрыт и не является отказом выдачи grant |

Это фактические CLI/engine/webhook результаты, не unit tests и не имитация
движка. Полный live S1, существующий OAuth/MCP и binary upload не проверены.

## N0 — source, установка и изоляция

Main до отчёта: 580c246f810446dfd4e17022eeecb1a3680e0340.
Прочитаны №13/комментарии, WORK-RULES, candidate/report S1, exact exports и
bootstrap. Другого claim не было; AGENTS.md/WORK-PARENT.json в дереве нет.
№10/12 и их зелёные проверки не повторялись.

Source S1: 2e7643bd805840f5ddba4d9836a8caf8fc6f508d.
Хэши до/после теста совпали с candidate:

| Файл | SHA-256 |
| --- | --- |
| pilot-bootstrap.cjs | 1ab2b0cf3397117ebb857b760253034db5449c2d21ed76a66915d5f94ff4d45b |
| upload-ledger.cjs | 81a4b3af7a15fe165fb7ca41b73dd228eb2ec57826b422064f2f40dc974f4401 |
| upload-grant.workflow.json | 8bf95f9e993e4ff494ad3cf90e86e694194366cb18c85496ec4e3abba9b3ff43 |
| owner-repository-upload.workflow.json | ae983561ed594a4fe0971c5b8b6be3a16eb87ac40311883d5ee7f34ed55a9c18 |

- Официальный источник: https://registry.npmjs.org/n8n/2.46.6 ,
  tarball https://registry.npmjs.org/n8n/-/n8n-2.46.6.tgz .
- n8n и n8n-nodes-base2.46.6; Node24.22.1, npm11.9.0, Python3.12.14.
  CLI --version действительно вернул2.46.6; требование package engines node>=24.
- Registry dist.integrity и clean lock entry совпали:
  sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==
- Lock v3: 2368entries, SHA256 7a73e18d8bf3feb36be6bc17919dd47b790d5bddaebf7305e215a8c146cac02d.
  Он реально использовался для фиксации resolved versions/integrity; временный
  lock удалён вместе с установкой, в отчёте оставлены hash и package metadata.
- Первый npm install --save-exact n8n@2.46.6 --no-audit --no-fund
  --fetch-retries=0 --fetch-timeout=20000 не завершился за300s.
  Это не объявляется успешным полным install. Из уже заполненного кэша
  --package-lock-only --ignore-scripts --offline построил clean lock.
- Обязательный sqlite3@5.1.7 не имел native binding; первый import отказал.
  Release-сборка достигла120s. Штатный node-gyp build --debug --jobs=2
  с cached headers24.22.1 завершился rc0; require(sqlite3) PASS, SQLite3.44.2.
  Источники dependency не патчились, downloads для сборки не требовались.
  Успех конкретных native путей не доказывает полноту всей npm dependency tree.

Использовалась только собственная папка0700; HOME сохранён. Для n8n сформирован
отдельный env без реальных credentials: отдельный N8N_USER_FOLDER/SQLite,
синтетический encryption key, diagnostics/version-notifications/templates OFF,
NODES_EXCLUDE=[], task runners internal, bind127.0.0.1 и временный port.
Docker/daemon не устанавливались; Railway image не запускался.

На первых startup обнаружены нежелательные DNS-попытки встроенного каталога
api.n8n.io, завершившиеся EAI_AGAIN, несмотря на отключённые diagnostics/templates.
Далее штатно заданы N8N_DISABLED_MODULES=mcp-registry,community-packages и
N8N_COMMUNITY_PACKAGES_ENABLED=false. В логах последних grant/snapshot startup
упоминаний внешнего каталога0. Это не скрывается утверждением «вообще не было
внешних попыток». Ни workflow, ни fixture не обращались к GitHub/Railway/live n8n.
Python runner в npm-среде не имел virtualenv; JS runner зарегистрировался и
выполнил нужный JavaScript Code. Python для этих workflow не требуется.

## N1 — native import/publish и readback

Команды подтверждены --help и первичными исходниками именно установленной
2.46.6: commands/import/workflow.js, commands/publish/workflow.js,
commands/execute.js и @n8n/db WorkflowRepository.publishVersion.
Help сначала был скрыт N8N_LOG_LEVEL=warn, затем прочитан при info.

В новой локальной БД выполнено:
1. import:workflow --input=upload-grant.workflow.json — rc0.
2. import:workflow --input=owner-repository-upload.workflow.json — rc0.
3. publish:workflow --id=workUploadGrantPilot — rc0.
4. publish:workflow --id=workOwnerRepositoryUploadV1 — rc0.

Исходные exports до этой проверки не адаптировались.

| ID | active | versionId = activeVersionId после clean publish |
| --- | ---: | --- |
| workOwnerRepositoryUploadV1 | 1 | d71cb4a0-01e8-4fed-aa7f-e6ffc7329ca5 |
| workUploadGrantPilot | 1 | af400079-8b60-4542-91cf-feab58eb624d |

Это узкое подтверждение clean import/publish в локальной среде.
Webhook/ExecuteCommand/JavaScript Code затем действительно исполнились в N2.
Полная native проверка всех типов binary workflow UNAVAILABLE из-за размера
служебного каталога; существование JSON не объявляется исполнением узлов.
Явное локальное NODES_EXCLUDE=[] позволяет ExecuteCommand. Bootstrap сам
не устанавливает это значение, реальные env values Railway здесь не читались.
JWT credential бинарного пути не выдавался и не использовался.

## N2 — native grant на вымышленных данных

CLI execute этой версии принимает id/rawOutput, но не произвольный fixture
input для webhook; выбран штатный loopback webhook.

Перед native выполнением отдельно прошли owner setup на127.0.0.1 с вымышленной
учётной записью и import:credentials с fake workPilotHeaderAuth. Ни пароль,
cookie, header value, raw grant, DB, ни полное execution data не публиковались.

Адаптация только в локальной копии grant:
- JSON path /nodes/1/parameters/command.
- В command заменён только /data/work/control/upload-ledger.cjs на
  /workspace/scratch/50ae5a91c977/native-n8n-13/ledger/upload-ledger.cjs.
- ID, узлы, соединения, Code, параметры и settings сохранены.
  Сам ledger скопирован exact bytes; UPLOAD_LEDGER_DIR указывает на свежий scratch.
  Адаптированная копия не выдаётся за неизменённый production export.

На отдельной свежей SQLite с owner setup до первого import/publish:
- POST /webhook/work-upload-grant-pilot-v1: HTTP200.
- Synthetic target markmalina/native-fixture-not-a-repository, вымышленные
  repositoryId/branch/uploadId, manifest одного пустого файла. GitHub не вызывался.
- Ответ сопоставлен с UUID/digest/target; hash raw token, TTL, fileCount1,
  totalBytes0 и target_json в свежем local ledger совпали.
- Без test header: HTTP403; с fileCount0: HTTP500. В grants осталась одна запись.
- Native execution_entity: webhook success1 и error1; отказ авторизации
  не создал дополнительный grant. Это реальная цепочка Webhook →
  ExecuteCommand → JavaScript Code внутри n8n.
- Raw token обработан только программно. Возвращаемый uploadUrl из source
  не использовался для upload.

Первый вспомогательный harness ожидал именно401 и вывел N2=FAIL при403.
Фактические данные этого прохода сохранены честно: positive200,
bindingVerified=true, localGrantHashBindingVerified=true,
unauthorized403, invalidBinding500, rows1. Для требования безопасного
отказа403 подходит; функциональный grant/binding PASS установлен по этим
наблюдениям, а не по ошибочной сводной метке harness. Запросы не повторялись
ради замены FAIL на зелёную строку.

## Важные ограничения раннего startup

Первый reimport активного workflow до owner setup отказал в deactivation
permissions. После штатного fake owner setup HTTP200 reimport/publish прошли.
Это локальная предпосылка; bootstrap уже содержит owner setup.

Далее в первой БД изменённый local grant получил
versionId/activeVersionId922c9189-2aef-42b8-925a-31a46928c39d, но runtime snapshot
ещё ссылался на af400079-8b60-4542-91cf-feab58eb624d. Ранний запрос после
/healthz/readiness исполнил старый /data path и вернул500 Cannot find module.
Таким образом readiness/CLI rc0 в тот момент не доказывали выбор новых bytes.

Дополнительный bounded startup с20 metadata samples в течение10s показал
сходимость publishedVersionId к922c9189-2aef-42b8-925a-31a46928c39d.
**Постоянный дефект CLI publication не подтверждён.** Раннее предположение
исправлено в checkpoint №13. Наблюдается окно между readiness и готовностью
нужного workflow snapshot; точная длительность окна отдельно не измерялась.

Минимальное предложение контроллеру для будущей приёмки S1: после запуска
проверять фактический published snapshot/исполнение ожидаемой версии и
metadata-only grant, а не только CLI rc0/activeVersionId/healthz. Если понадобится
startup barrier в source, рассмотреть его отдельно с native regression.
Здесь такой код не написан, candidate/pending не менялись.

## N3 — cleanup и остаток

Свои локальные n8n/JS runner процессы остановлены через собственные process groups
и wait; terminal results получены. Удалены только собственные временные
установка, обе SQLite, ledger, fixtures, cookies/keys, логи с execution data и
тестовые scripts. Отсутствие временной папки подтверждено. Сохранены только
безопасные metadata этого отчёта; production/user payload отсутствуют.

npm Debug build/Linux/Node24.22.1 не объявляется эквивалентом
docker.n8n.io/n8nio/n8n:2.46.6: image digest, ABI и среда Railway здесь не
проверялись. Нет real credentials, подключённого n8n MCP/OAuth, uploads,
Deploy/restart/permissions/pending/volume/SQLite/server mutations.
Source hashes неизменны; №10/12 не повторялись, соседние repos не менялись.
Нового hosted CI нет, source не менялся.

Live S1/№9 остаётся BLOCKED и не завершён: установленный code/runtime,
running1, persistent mode, сохранность live journal и grant через прежний OAuth
ещё требуют собственной разрешённой проверки. Полный S2 и S3–S6 не выполнялись.
№13 оставить открытой. Межчатовая доставка/приёмка не имитируются.

ДАЛЬШЕ: контроллер — принять native свидетельства и ограничения №13 и учесть окно готовности snapshot в продолжении №9.


---

## Приёмка контроллера — 07.11.2026,16:10МСК

**№13 / S1.N ПРИНЯТА как ограниченная локальная native проверка.** Живой S1 не принят.

Контроллер прочитал все checkpoints и этот отчёт. Проверен commit f82067b0eef5bc7da33d11e1f0508e20fecb2a37: parent580c246f810446dfd4e17022eeecb1a3680e0340, добавлен только REPORT.md. Product source, S1 candidate и workflow exports не менялись. Дополнительно прочитан exact bootstrap2e7643bd: он вызывает штатный publish:workflow и сохраняет окружение; собственного NODES_EXCLUDE не задаёт. Это соответствует отмеченной границе локального теста с NODES_EXCLUDE=[].

Принимаются раздельные наблюдения исполнителя:
- Native n8n2.46.6 import2/2 и publish2/2: четыре команды rc0, локальные active/version bindings проверены.
- Native grant на отдельной fresh SQLite после fake owner setup: HTTP200 и сверка response/local ledger.
- Запрос без header отвергнут403; невалидный count —500 без новой строки grant. Это узкая проверка отказа; удобство/классификация ошибок и полный upload-путь не приняты этим этапом.

Не превращаются в PASS:
- Полный native catalog types — UNAVAILABLE (>16MB предела probe).
- Сводная метка harness — FAIL из-за неверного ожидания401. Проверяемые200/binding/ledger и403 рассмотрены отдельно; исходная метка не переписана.
- Ранняя update-попытка после readiness исполнила старый snapshot и вернула500. Поздняя DB-сходимость не доказывает, что в том же update-сценарии после неё фактически исполнилась новая версия: такого повторного execution в отчёте нет. Успешный grant относится к отдельной fresh DB.
- npm Debug sqlite build не равен установленному Railway image, полный npm dependency tree не объявлен проверенным.

Постоянный дефект публикации по этим наблюдениям не установлен. Положительные native результаты принимаются как датированные свидетельства исполнителя с сохранёнными metadata; контроллер не запускал повторно удалённое временное окружение и не проверял live сервис.

### Уточнение живой приёмки №9

1. Проверить effective доступность нужных native node types/несекретную конфигурацию, в частности ExecuteCommand. Локальный тест с NODES_EXCLUDE=[] не доказывает текущее значение Railway.
2. После разрешённой установки не считать CLI rc0/activeVersionId/healthz достаточным успехом. Подтвердить ожидаемые published snapshot/version и source bytes двух workflow штатным readback, с ограниченным ожиданием сходимости. Не вводить произвольный fixed sleep как доказательство.
3. Без передачи файлов пройти metadata-only grant на synthetic manifest/target и подтвердить фактически исполненную ожидаемую версию и binding. Сырой token/execution payload не выводить в модель/публичные отчёты.
4. При несовпадении/stale snapshot — не начинать пользовательские upload, вернуть точное расхождение. Отдельный source barrier нужен только по подтверждённому дефекту/контракту; здесь production-код не меняется.
5. Невозможность полностью выдать catalog не заменяет отдельную проверку необходимых типов/маршрута. Каталог не перечитывать без конкретной потребности; binary workflow действительно испытывается в S2 после S1.

Ответ поддержки19384733 перепроверен в текущей почтовой цепочке: только прежнее письмо13:58МСК и наши уточнения14:44МСК. Нового разъяснения допуска в этой цепочке нет. Railway/permissions/pending/volume/SQLite/n8n не опрашивались и не менялись в ходе этой приёмки. Дополнительные native/CI/внешние jobs не запускались. Новых задач реализации ради подготовки не создано.

ДАЛЬШЕ: контроллер — закрыть №13 и сохранить уточнённые критерии в №9; поддержка OpenAI — продолжить разбор допуска.
