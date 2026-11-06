# GitHub App: создан, ключ и установка заблокированы

06.11.2026, около 14:26–14:30 МСК. Владелец подтвердил создание и установку отдельного GitHub App для n8n с Contents read/write и обязательным Metadata read, первоначально только на `markmalina/freelance`. Разработка/платный пилот повторно не согласовываются.

## Подтверждено

В ранее подготовленной форме нажата Create GitHub App. GitHub показал Registration successful и страницу настроек:

- Name/slug: `markmalina-n8n-upload`.
- Owner: `markmalina`.
- App ID: `5641721`.
- Client ID (публичный идентификатор, не secret): `Iv23likO8VAgK2JNXJzI`.
- Settings: https://github.com/settings/apps/markmalina-n8n-upload .
- Подготовленная и отправленная конфигурация: Contents read/write, mandatory Metadata read; остальные права No access; Only on this account; Webhook inactive; user OAuth/device flow не запрашиваются.

GitHub сообщил, что для установки сначала нужен private key. Открыта штатная страница https://github.com/settings/apps/markmalina-n8n-upload/key_pairs . До действия New key она показывала Key pairs 0.

## Точный блокер

При New key облачный браузер отклонил действие своей URL policy: requested URL protocol is not allowed; allowed protocols http/https. Блокировка принадлежит среде браузера, это не ошибка OAuth GitHub/Railway и не доказательство недоступности GitHub.

После блокировки не удалось даже повторно прочитать состояние этого tab. Попытка штатного requestUserTakeover также отклонена той же URL policy. Обход через другие browser surfaces, raw CDP, скрытые HTTP mutations или альтернативный путь создания того же ключа не выполнялся.

Поэтому создание пригодного ключа не подтверждено, private key не получен, установка App на freelance и доступ Git из n8n не выполнены. Нельзя утверждать, что после блокировки keys count остался нулевым: последнее подтверждённое нулевое значение было ДО New key.

Снять новый screenshot созданного App после блокировки также не удалось. Предыдущий screenshot `github-app-permissions-draft-2026-11-06.jpg` подтверждает только подготовленные права, не итоговую установку.

## Минимальное ручное продолжение

Владелец открывает штатную страницу key pairs, создаёт пригодный private key и сохраняет его как secret variable `GH_APP_PRIVATE_KEY` только в service `n8n-upload` / environment `pilot` указанного Railway project. Значение — полный PEM с исходными переводами строк, не Base64 и не публичный ключ. Секрет нельзя присылать в переписку или сохранять в Git.

Railway service (проверенный URL кабинета): https://railway.com/project/69cc90c9-7ede-4a57-bc03-f3e63f01cca3/service/2425a11a-90bd-47fe-9c5b-03ad96ee7a74?environmentId=369d5bb9-5107-4e39-89d8-668b9b59e230 . Нужна вкладка Variables. Если UI предлагает сохранить без deployment, выбрать этот вариант: compute пилота остановлен до продолжения работы.

После подтверждения сохранения исполнитель продолжает уже разрешённую установку только на freelance, проверяет реальные granted permissions/repository selection и программно использует secret без вывода значения. Затем выдаёт короткий installation token и проверяет Git на отдельной тестовой ветке. GitHub App installation token и Git authentication пока не проверены.

Если ручное создание ключа также требует дополнительной авторизации, её выполняет владелец. Новое согласование того же состава прав не требуется. Расширение на другие репозитории в это подтверждение не входит.

## Остальной статус

Вычисления Railway оставались остановленными в этом ходе, ресурсные mutations и новая подписка не выполнялись. Подтверждённый ранее Work → n8n transport (100 files / 30 MB, SHA-256, restart) остаётся в LIVE_PILOT_2026-11-06.md. Полный GitHub upload по-прежнему не принят.
