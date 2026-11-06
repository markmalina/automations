# Проверка нового Work и исправление хранения — 06.11.2026

Статус: **SMALL_UPLOAD_PASS / BATCH_DISK_FAILURE / FIX_READY_FOR_DEPLOY**.

## Проверено из этого Work

Подключённый личный plugin n8n GitHub Upload: https://chatgpt.com/plugins/plugin_asdk_app_6aedee88e8d481919091aad0f73bc28f?directoryTab=personal . OAuth scopes: workflow:read, workflow:execute, execution:read. В новом Work обнаружены реальные инструменты n8n. Постоянные ключи/пароли/pilot header из прежнего Work не переносились. Grant получен программно через MCP, во временный локальный файл mode 0600; значение не печаталось и не сохранялось в Git. Передача bytes — HTTPS multipart из executor, без Base64 через модель и без pin/mock data.

| Проверка | Результат |
|---|---|
| MCP get_workflow_details → execute_workflow → get_workflow_execution | PASS, grant execution 37, затем 40; опубликованная выдача реального разрешения |
| Один бинарный файл 300,000 bytes | PASS, HTTP 200; до квитанции 35.400234 s |
| GitHub exact-commit readback | PASS, побайтовое совпадение и Git blob SHA; source SHA-256 065b02fcf41db00951f3f4e05595798e1f329c92dc94335a651b26e6ce379c26 |
| Повтор того же ID/manifest/bytes | PASS, 9.331025 s, replayed=true, тот же SHA, ветка не получила второй commit |
| 100 файлов / 30,000,000 bytes, те же bytes, что в direct benchmark | FAIL, HTTP 500 после 26.513647 s; от начала выдачи grant до отказа 36.753253 s |

Коммит файла: https://github.com/markmalina/freelance/commit/0fd7208ff8f56c8b9d381861899a66c8bdf3fc39 . Тестовая ветка test/n8n-upload-20261106. GitHub показывает 1 added path, 0 modified/removed; родитель 9c9e4a262de79ac9bd35bab14121ae8fd09b598b. После повтора и отказа большого комплекта remote head по-прежнему 0fd7208f… .

Неуспешный комплект: upload ID 9d94bcf3-9a28-4014-93d5-ce8e5d259c7d, digest c70e309b44dd36290d14dfec7434bd6fde1616c48c3b294809b98aa57c1a2455. Он не повторялся вслепую; его журнал/claimed/uncertain не удаляется и не сбрасывается исправлением. Проверенный native Git clone не дошёл до checkout: runtime log 15:30:15Z — No space left on device, Clone succeeded, but checkout failed. Точный failed temp: /data/work/.n8n-clone-16b4d4c47d6b593ddfcb6b82.

## Сравнение скорости

Прямой connector ранее сохранил 100/30MB за 86.392 s, readback 17.864 s; SHA-256 всех 100 подготовленных исходных файлов здесь совпадают с тем benchmark corpus (salt 202611061621). У n8n успешного нового замера этого комплекта нет. 26.51 s — время до отказа, не скорость выгрузки. Коэффициент ускорения не установлен.

При будущем парном тесте указать порядок: GitHub может дедуплицировать одинаковые blobs при второй передаче. Нужен новый corpus и чередование порядка маршрутов для устойчивого сравнения. Один успешный файл не заменяет приёмку 100 файлов.

## Исправление

- После durable confirmed удаляется только одноразовый clone соответствующего upload ID. Journal/receipt/commit SHA остаются; replay не требует локальной копии.
- Startup prune-confirmed освобождает старые подтверждённые копии. Claimed/uncertain и committed без подтверждения не очищаются.
- Отдельная разовая allowlist-процедура для указанной неудачной временной копии: проверяет имя, настоящую директорию без symlink, origin ровно freelance и HEAD reflog только clone без локальных commit/reset/rebase/merge. Helper может исполняться из stdin до записи новой версии, чтобы освободить место при заполненном диске.
- Выдаваемый grant направляется на work-fresh-token-upload-pilot-v1; ручная подмена endpoint больше не нужна после установки.
- UPLOAD_SERVICE_MODE=persistent явно выключает прежний таймер. По умолчанию сохранён bounded pilot. Неожиданный выход n8n отдаётся Railway как ошибка; предлагается ON_FAILURE, максимум 3 повтора. Файлы БД/credentials/OAuth остаются на том же volume, размер/лимиты не увеличиваются.

Проверки: node --check обоих CJS; существующие 16 конкурентных SQLite claims, конфликт digest, replay, неверные/истёкшие grants; новый test_upload_retention.py проверяет подтверждённую очистку, сохранение receipt/uncertain/unconfirmed, symlink и чужой origin/локальный commit, stdin-maintenance и canonical endpoint; test_upload_bootstrap.cjs проверяет отсутствие watchdog в persistent и сохранение bounded/expired поведения. Все выполнены локально успешно. Live применение/повтор 100-file проверки ещё НЕ выполнены.

## Применение и остаток

Кандидат предназначен для существующего сервиса n8n-upload / pilot, без новых services/volumes. Подготовка изменений не равна установке. После Deploy проверить UPLOAD_SERVICE_READY persistent, startup cleanup results и UPLOAD_DISK_BYTES, running replica/health, OAuth tools; затем самостоятельный новый тест 100 файлов. Исходный failed ID сохранить для отдельного восстановления, не обходить его результат новым ID под видом retry.

Остаются production-критерии из RETRY_ACCEPTANCE: универсальные разрешённые назначения, восстановление незавершённых commit/push, hardening путей/attributes/размеров, HTTP status/result, backup и silent OAuth refresh. Проект не объявляется полностью принятым.
