# Отчёт проверки — 05.11.2026, МСК

## Выполнено

- Создана отдельная issue #8 и ветка `infra/n8n-github-upload-8` в приватном `markmalina/freelance`; issue #7 не используется.
- Из текущего Work проверены команды и HTTPS, изучены доступные подключения, текущий Ops и штатные компоненты n8n.
- Подготовлены диагностический export, конфигурация самостоятельного размещения, инструкция и проект требований к будущей пакетной обработке.

## Проверено фактически

| Проверка | Результат | Ограничение |
|---|---|---|
| Команды в текущей Work-среде | Python, curl, git доступны | Не доказательство доступности во всех следующих Work |
| HTTPS HEAD docs.n8n.io | 302 | Документация, не n8n webhook |
| HTTPS HEAD api.github.com | 200 | Публичный API без доказательства private git auth |
| HTTPS raw binary POST Work → httpbin.org | 200, 1024 байта, SHA-256 совпал | Синтетический echo, не n8n и не GitHub |
| Исходный/возвращённый SHA-256 echo | `785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9` | Только эти 1024 байта |
| Полное время echo | 5.418 s | Не замер производительности целевого маршрута |
| Work → postman-echo.com POST | 403, Cloudflare error 1010 | Не policy denial и не доказательство блокировки n8n |
| GitHub connector → private freelance | metadata/push permission; создание issue и ветки подтверждено | Credential connector не доступен автоматически n8n |
| n8n версия | npm latest на момент проверки 2.46.6 | Образ не запускался |
| Export Webhook параметры | Имена параметров сверены с исходником тега n8n@2.46.6 | Импорт/выполнение не проверены |

Секреты не выводились и не копировались из инфраструктуры других проектов. На сторонние echo endpoints передавались только синтетические данные.

## Локальная проверка подготовки

Python syntax проверен через AST; JSON export разобран, неактивное состояние, Header Auth и отсутствие экспортированных credentials проверены статически. Запуск probe без secret bindings завершился ожидаемым отказом до сетевого обращения. Это не тест n8n и не сквозная приёмка. Docker build и compose runtime не выполнялись.

## Блокер

Нет подтверждённого HTTPS n8n endpoint и разрешённого административного подключения/target для его создания. У текущего Work нет найденной защищённой постоянной привязки webhook credential для будущих Work. Не установлены Docker/n8n; deployment build и серверные файловые/Git операции не выполнялись.

Сетевой запрет для n8n **не установлен**: известного адреса n8n для проверки нет. Нельзя подменять отсутствие target утверждением о блокировке сети.

Минимальное действие владельца: указать/предоставить один разрешённый n8n/серверный target с административным каналом; при дополнительных расходах согласовать бюджет. Значения секретов не присылать в чат. После выбора target определить защищённую привязку credential к обычному и следующему Work и выполнить `probe_work.py`.

## Сквозная приёмка: всё ниже НЕ ПРОВЕРЕНО

| Критерий | Статус |
|---|---|
| Один binary Work → n8n → private GitHub, SHA-256 roundtrip | NOT_RUN |
| ~100 смешанных файлов / ~30 MB, пути и SHA-256 каждого | NOT_RUN |
| Один commit и push без ZIP | NOT_RUN |
| Кириллица, пробелы, вложенные папки | NOT_RUN |
| Обновление без изменений посторонних файлов | NOT_RUN |
| Обрыв ответа и idempotent retry | NOT_RUN |
| Конкурирующие комплекты без смешивания | NOT_RUN |
| Перезапуск n8n, восстановление журнала и Git | NOT_RUN |
| Повтор в новом обычном Work из Android | NOT_RUN |
| Раздельные замеры upload / processing+push / total | NOT_RUN |

Текущий способ загрузки сохраняет силу. Ускорение не заявляется.

## Первичные источники

- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.git/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.readwritefile/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/
- https://docs.n8n.io/hosting/installation/docker/
- https://docs.n8n.io/connect/connect-to-n8n-mcp-server/
- https://developers.openai.com/plugins/reference
- https://docs.railway.com/pricing/plans
- https://registry.npmjs.org/n8n/latest (версия 2.46.6 на момент проверки)
- https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/nodes-base/nodes/Webhook/description.ts
- https://github.com/markmalina/ops/blob/cf849c8eddc50035ad57e711610b3dd4578c9ae5/AGENTS.md
- https://github.com/markmalina/ops/tree/cf849c8eddc50035ad57e711610b3dd4578c9ae5/agent-ops/registry/targets

MCP n8n в этой сессии не подключён; его фактическая схема/файловый вход не проверялись. Для выбранного raw HTTPS probe MCP не требуется.
