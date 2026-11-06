# Подключение n8n Upload к Ops — 06.11.2026

Статус: **CONFIG_EXECUTOR_SOURCE_READY**, живой маршрут не выпущен.

Ops: https://github.com/markmalina/ops/commit/40aab72a36dcf5ed018fa0391f3d5a04e4a596df .
PR: https://github.com/markmalina/ops/pull/435 .
Задача: https://github.com/markmalina/ops/issues/434 .

## Реализовано

Код `agent-ops/n8n-upload/` содержит проверку подписанного плана и отдельного
одобрения владельца, фиксированный адаптер Railway ChangeSet с baseConfigEtag,
журнал на отдельной Git-ветке и независимый проверяющий модуль.

Состояния: CLAIMED → SUBMITTING → SUBMITTED → OBSERVED → VERIFIED.
Журнал подтверждается удалённым Git до вызова Railway. Конкурирующая запись
использует non-force parent-bound update. После обрыва или неизвестного результата
новый apply блокируется, в том числе с новым request ID. Подтверждённая квитанция
повторяется без второго deploy.

Результат Railway SUCCESS даёт только OBSERVED. Для VERIFIED требуется отдельное
подписанное наблюдение из другого run: точное deployment ID, runtime hashes двух
файлов, health/readiness, persistent mode, доступный диск и сохранность журнала.
Проверяющий модуль не содержит токена или графа мутаций Railway.

110 offline tests PASS, Node syntax checks PASS. Native API shape сверена с
официальным railwayapp/cli@5a07ac2ae44ec2fcf892ba96e18f638402c7f8fb. Это проверка
исходников API, а не живая приёмка provider capability.

## Клиентская привязка

`agent-ops.lock` закрепляет exact Ops commit и SHA-256 candidate/project.
`.agent-ops/project.yml` — JSON, совместимый с YAML. Workflow
`ops-n8n-preflight.yml` допускает только /n8n-ops preflight от точного владельца
на issue #1, первый run на main. Все action refs — полные SHA, permissions —
contents:read/issues:read. Ни secrets, ни protected Environment нет.

Клиент по-прежнему вызывает только onboarding preflight, возвращающий
ABORTED/E_NOT_RELEASED для корректного кандидата. Новый executor не подключён
к этому workflow; команда deploy не добавлена.

## Что блокирует живой запуск

- source/client acceptance и выпуск защищённых requester/control/observer workflows;
- аутентифицированная GitHub/OIDC-привязка планов, одобрения и observation;
- доказанный доступ к точному project/environment и права на журнал;
- native disposable-fixture acceptance экспериментального ChangeSet API;
- отдельный сборщик достоверного runtime observation.

`release.json` enabled=false, bindings=null, mutationBudget=0. Код не создавал
credential, signing key или journal branch. Фикстуры подписей создаются временно
в памяти тестов; новые постоянные секреты этим кандидатом не предписываются.

Адаптер отклоняет любую staged-конфигурацию, включая прежний pending patch.
Он не применяет и не удаляет отклонённый auto-review эффект через иной маршрут.
Таймер и runtime n8n этой работой не изменены; прежний срок 19:41:59 МСК уже
прошёл, текущее состояние compute здесь не проверялось.

Retention fix: https://github.com/markmalina/automations/pull/3 .
Failed upload ID 9d94bcf3-9a28-4014-93d5-ce8e5d259c7d сохраняется.
