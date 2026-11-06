# Проверка доступа Ops к n8n

Один служебный Railway project/environment token уже сохранён в Environment
`n8n-upload-readonly`; разрешена только ветка `main`. Для новых Work этот токен
не создаётся заново и в чат не передаётся. Пользовательское OAuth-подключение
n8n и существующий GitHub App сохраняются.

Команда `/n8n-ops inspect` в Automations issue1 запускает два коротких job:
сначала проверка автора23397294, репозитория1448151721, main, exact SHA,
исходного неотредактированного комментария не старше5минут и attempt1;
затем один фиксированный запрос Railway из защищённого окружения. Первый job
не получает provider credential. Оба checkout читают только собственный
репозиторий через временный GITHUB_TOKEN. Новые source-access App/keys и
открытие приватного Ops для других репозиториев не требуются.

Источник reader/profile: immutable Ops commit
`6e8598bddf7b33a9cda65efab878fff994048176`.
`ops-scope.lock.json` и verifier закрепляют SHA-256 обоих файлов до импорта
reader. Локальные копии соответствуют центральному рассмотренному исходнику.

Читаются только projectId/environmentId проектного токена, service/environment
ID и metadata последнего deployment. Никаких variables/config/logs,
introspection, произвольных query/targets, mutation или Deploy. Максимум один
provider request,15секунд,64КиБ ответа, без перехода по redirect.

Результат `OBSERVED_NOT_ACCEPTED` подтверждает только наблюдаемые поля и
`scopeAccepted`. Metadata SUCCESS не доказывает работающую compute. Постоянный
режим, свободный диск, сохранность runtime journal и возможность штатного
развёртывания принимаются отдельно живыми проверками.

Старые PR3/4/5 и Ops435 не объединяются автоматически; их выключенные
read/mutation release records не меняются этой установкой. Прежний отказ
railway_accept_deploy не отменяется и не обходится. Failed upload ID
`9d94bcf3-9a28-4014-93d5-ce8e5d259c7d` и журнал не сбрасываются.

Основные задачи: https://github.com/markmalina/ops/issues/434 и
https://github.com/markmalina/automations/issues/1 .
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md .
