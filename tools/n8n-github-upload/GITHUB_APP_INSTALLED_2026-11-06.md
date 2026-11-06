# GitHub App установлен; запуск проверки ключа ожидает разрешения инструмента

06.11.2026, около 15:01–15:05 МСК.

## Выполнено и проверено

Владелец сообщил, что заменил значение переменной содержимым PEM. `get-staged-changes` подтвердил одну недеструктивную pending mutation: добавление `GH_APP_PRIVATE_KEY` для service `n8n-upload` в environment `pilot`. Содержимое скрыто; валидность PEM этим не доказана. Patch ID: `938b9fdc-03bb-41bc-b5a7-5ed874ab9af7`.

Завершена ранее разрешённая установка GitHub App `markmalina-n8n-upload`:

- App ID `5641721`.
- Installation ID `179245428`.
- Installation settings: https://github.com/settings/installations/179245428 .
- Repository selection: **Only select repositories**, выбран ровно один `markmalina/freelance` (repository ID `1378687935`).
- Granted permissions в итоговой странице: Read access to metadata, Read and write access to code.
- GitHub показал успешную установку. Screenshot: `evidence/github-app-installed-freelance-2026-11-06.jpg`.

Создание ключа через ранее заблокированный New key не повторялось. Установка — отдельное действие после ручного создания ключа владельцем, с ранее подтверждённым составом прав.

## Подготовка runtime-проверки

`pilot-bootstrap.cjs` дополнен проверкой `GH_APP_PRIVATE_KEY` внутри контейнера:

1. Node crypto читает PEM и проверяет RSA type.
2. Вычисляет публичный fingerprint.
3. Подписывает короткий GitHub App JWT с App ID 5641721.
4. Вызывает штатный GET https://api.github.com/app и сверяет App ID/slug.
5. Сохраняет/печатает только identity, public fingerprint, permissions и время проверки. Private PEM/JWT/token не выводятся.

Код проверен `node --check`; реальный запуск этой проверки ещё НЕ выполнен. Изменённая программа bootstrap сохранена в переменной сервиса через set-variables(skipDeploys=true), без запуска. Ранее действующий абсолютный deadline пилота 15:45:16 МСК не продлевался.

## Блокер запуска

Попытка применить один pending secret через `accept-deploy` отклонена автоматической проверкой разрешений. Точный ответ: `Cancelled — the user did not approve this action. No changes were made.`

Несмотря на прежнее подтверждение пилота и реплику «Сделал», инструмент не принял их как достаточное подтверждение именно применения pending changes и запуска. Повторный вызов или обход через UI/другой API не выполнялся.

Readback list-deployments: успешные предыдущие deployments REMOVED; активных SUCCESS/DEPLOYING нет. Значение private key остаётся pending. Проверка GitHub App JWT, installation token, git clone/commit/push не выполнялись.

Для продолжения требуется явное подтверждение владельца: **«Применить ожидающее изменение GH_APP_PRIVATE_KEY и запустить n8n в рамках согласованного пилота до $1»**. Новая подписка/дополнительный сервис/расширение GitHub scope не предлагаются. При истечении абсолютного deadline не продлевать его молча.

После разрешённого запуска: проверить fingerprint/identity, выпустить ограниченный installation token, проверить доступ к отдельной тестовой ветке freelance. Установка приложения сама по себе не заменяет эту проверку и полную приёмку загрузчика.
