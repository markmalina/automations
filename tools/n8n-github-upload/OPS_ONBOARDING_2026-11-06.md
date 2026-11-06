# Подключение n8n Upload к Ops

Статус: **SOURCE_CANDIDATE**, живой deploy через Ops не подключён.

Ops source: https://github.com/markmalina/ops/commit/0ff69fc58cb6cb6a70f68d2c01e986628b98ab2c .
Review: https://github.com/markmalina/ops/pull/435 .
Задача: https://github.com/markmalina/ops/issues/434 .

`agent-ops.lock` закрепляет exact Ops commit, SHA-256 центрального candidate и
локального project reference. JSON в `.agent-ops/project.yml` является допустимым
YAML. Workflow `ops-n8n-preflight.yml` обрабатывает только точную команду
`/n8n-ops preflight` от владельца на Automations #1, первый run на main.
Разрешения — только contents:read и issues:read; protected Environment и secrets
не используются. Проверка создаёт безопасный JSON-отчёт и завершается ABORTED:
правильный ввод даёт E_NOT_RELEASED, а не успешное развёртывание.

Workflow пока находится в draft PR. Не публиковать команду, ожидая живого запуска,
до source/client review и установки на main.

## Что подготовлено

- Точные наблюдённые project/environment/service/volume IDs n8n и 6 полей
  предлагаемого изменения: два файла из retention commit, persistent mode,
  один failed temporary clone, ON_FAILURE и максимум 3 повтора.
- Контроль полного SHA, digest файлов контрактов, личности владельца,
  номера issue, команды и rerun. Данные credentials не читаются.
- 52 локальных поведенческих теста центрального кода. Отдельно проверяется
  фактический запуск CLI с этими клиентскими файлами.
- Центральные 5 файлов прочитаны по exact commit и сверены с подготовленными.

## Что остаётся

Это проверка подключения, не обработчик применения конфигурации.
Следующий рассмотренный шаг — отдельные requester/control/verifier и
типизированный config executor, свежий preflight и план, допустимое approval,
доказанный доступ к точному n8n project/environment и независимая проверка.
Наличие подходящего project token в Ops пока не доказано; значения существующих
секретов не запрашивались и не копировались. Вызов существующего Gate/AQUB executor
для n8n запрещён его собственной привязкой.

Предыдущий railway_accept_deploy отклонён автоматической проверкой. Подключение
Ops не служит способом обойти этот отказ. Отдельный код проверки не применяет
staged patch, не меняет таймер, лимиты или размер диска, не запускает upload.
Старый срок 06.11.2026 19:41:59 МСК остаётся фактом прежней конфигурации;
после него состояние нужно читать заново.

Retention fix и прежняя проверка выгрузки:
https://github.com/markmalina/automations/pull/3 .
Неудачный upload ID 9d94bcf3-9a28-4014-93d5-ce8e5d259c7d сохраняется.
