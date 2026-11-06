# Подключение n8n Upload к Ops — 06.11.2026

Статус: **PROTECTED_SOURCE_PREPARED / LIVE_BLOCKED**. Постоянный сервис не включён.

Ops commit: https://github.com/markmalina/ops/commit/8d50065a688f675a1d9bdf1a7d30a9c8ede425c5
PR435: https://github.com/markmalina/ops/pull/435
Основная задача: https://github.com/markmalina/ops/issues/434
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md

В исходниках есть фиксированный configuration executor, Railway ChangeSet adapter,
durable Git journal и независимый verifier. Добавлена аутентификация подписанных
role artifacts через GitHub run/actor/source/workflow/comment и скачанный
artifact digest. Ключ из запроса без таких доказательств не принимается.
Временные ключи не сохраняются; секреты и OIDC tokens в артефакты не помещаются.
Фактический control run записывается отдельно от завершённого approval run.

170 offline behavioral tests PASS; 11 MJS syntax checks PASS. Реальный CLI
защищённого чтения возвращает ABORTED/E_READ_NOT_RELEASED, providerRead=false,
secretAccessed=false. Это локальная проверка, не живой доступ Ops к Railway.

## Клиент

agent-ops.lock и preflight workflow закрепляют указанный полный Ops SHA.
Команда /n8n-ops preflight остаётся provider-free, ABORTED/E_NOT_RELEASED.

Добавлен отдельный /n8n-ops inspect на issue1. agent-ops.read.lock и
.agent-ops/read-project.json связывают full SHA, target, operation и read-release.
Первый job без provider credentials; условный второй job имеет фиксированный
protected Environment n8n-upload-readonly и только named project token.
Сейчас read-release.enabled=false/sourceAcceptance=PENDING: защищённый job
не допускается. Environment/credential не создавались, их наличие неизвестно.
Workflow находится в draft PR, на main обработчика ещё нет.

## Фактическое состояние

В read-only наблюдении около 20:44 МСК: точный сервис, metadata SUCCESS/Online,
но running=0 из 1. Лог PILOT_DEADLINE_REACHED — 19:42:02 МСК. Старый deadline
19:41:59 МСК не продлевался. Patch 0bfc3cd0-278a-4e41-b1f1-7df8cb385602
остаётся STAGED: шесть полей/пять native операций, не применён и не очищен.

Существующее OAuth-подключение использовано: get_workflow_details для
workUploadGrantPilot снова вернул Internal error. Execution/grant не выдан.
Причина ошибки коннектора не установлена. Пароль/секреты/повторный OAuth
не запрашивались. Наблюдение через connector не доказывает scope Ops credential.

## Блокеры живой приёмки

Предыдущий automatic deploy rejection остаётся обязательным ограничением.
Повтор/эквивалентный deploy через Ops, браузер или CLI не выполнялся.

Также остаются независимая source/client acceptance, установленные защищённые
planner/approval/control/observer workflows, принятые bindings и scopes, native
disposable-fixture acceptance, owned journal access/concurrency и источник
достоверного runtime observation. Новый read-only collector не импортирует
граф мутаций и не выдаёт HTTP200 за runtime hashes/disk/persistent/journal proof:
эти поля остаются null. Main и release политики не включены.

Retention fix — PR3, d1abb31147db3d0bd1f7ffbec0c1b6dbffbfeb67.
Failed upload ID 9d94bcf3-9a28-4014-93d5-ce8e5d259c7d сохранён.
Новые бинарная/replay/100-file приёмки до допустимого восстановления compute
не выполнены. Полный source-протокол и остаток:
https://github.com/markmalina/ops/blob/8d50065a688f675a1d9bdf1a7d30a9c8ede425c5/docs/runbooks/n8n-upload-protected-launch.md


Дополнение: отдельный runtime successor PR5 — https://github.com/markmalina/automations/pull/5 , commit e2d0b82ef9c00d4f96ef657c8a29e4b4689fb4f9. Он измеряет source/disk/journal после очистки, но не выбран текущим Ops candidate и не установлен. Новый fixed read-only collector в Ops сохраняет runtimeSampledAt отдельно от observedAt и возвращает OBSERVED_NOT_ACCEPTED; существующий verifier не принимает его формат за VERIFIED. 23 новых collector tests и 10 runtime SQLite tests PASS; старый staged patch/d1abb311 и принятые hashes не подменялись. Нужны отдельные protocol/source/log-provenance/native acceptance.
