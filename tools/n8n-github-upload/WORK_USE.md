# Использование из нового Work

OAuth plugin **n8n GitHub Upload** создан, установлен и подключён 06.11.2026. Карточка: https://chatgpt.com/plugins/plugin_asdk_app_6aedee88e8d481919091aad0f73bc28f?directoryTab=personal . В новом сообщении/Work выбрать его через @. Нужны только workflow:read, workflow:execute, execution:read. Пароль n8n и GitHub private key между чатами не передаются.

Фактическая приёмка нового Work и оставшиеся ограничения: NEW_WORK_CHECK_2026-11-06.md. Один файл и replay PASS; новый 100-file тест упёрся в disk failure. Исправление очистки и persistent mode в этой ветке — кандидат, до Deploy не установлено. До полной приёмки прежний GitHub connector сохраняется.

Текущий пилот разрешает только markmalina/freelance, test/n8n-upload-20261106, prefix n8n-retry-tests/<uploadId>. Это ещё не универсальный interface repo/branch/path.

1. Прочитать get_workflow_details для workUploadGrantPilot. Создать в executor UUID и manifest {uploadId,files:[{field,path,bytes,sha256}]} (100 файлов, <=32,000,000 bytes). Digest — SHA-256 recursively key-sorted compact UTF-8 JSON, порядок files сохранён. Проверять реальные размеры и hashes. UUID сохраняется для повторов.
2. Через execute_workflow намеренно запустить опубликованную выдачу grant: executionMode=production, triggerNodeName=OAuth grant input, inputs.webhookData={method:POST,body:{id,digest,fileCount,totalBytes}}. Это выдача реального разрешения на порученную загрузку, не тестирование workflow-кода. Получить executionId, затем get_workflow_execution includeData=true,nodeNames=[Return temporary grant],truncateData=1. До success/выданного grant ничего не загружать.
3. Полученный token не печатать, не передавать через модель, не класть в Git/командную строку; программно сохранить только краткоживущие поля в локальный файл 0600. MCP передаёт только metadata; файлы идут напрямую по HTTPS multipart: manifest + binary parts, X-Work-Upload-Grant.
4. После применения исправления grant.uploadUrl — канонический свежий-token endpoint. До установки исправления старый grant возвращает более ранний endpoint: для проверенного пилота единственная явная разрешённая замена — https://n8n-upload-pilot.up.railway.app/webhook/work-fresh-token-upload-pilot-v1 . Не следовать произвольным URL и редиректам.
5. Проверить success, точные uploadId/count/bytes/repo/branch/commit SHA. Прочитать GitHub ref/историю, скачать exact commit и сравнить bytes/SHA-256. Потеря ответа — не доказательство неуспеха. Повтор использует тот же UUID/manifest/bytes; ID_CONFLICT/uncertain не сбрасывать и не обходить новым ID.
6. После Deploy исправления confirmed clone очищается, receipt/commit остаются. Старый неуспешный batch остаётся в журнале для восстановления. Наличие плагина/HTTP200 не равно полной production-приёмке.
