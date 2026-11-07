# Автономная ночь n8n — 08.11.2026

Прямое поручение Марка: довести реальную binary загрузку из любого обычного Work через n8n в назначенный репозиторий markmalina до commit URL и независимого чтения удалённых bytes по exact commit SHA. Это исполнение работы, не напоминание владельцу.

Регламент каждого назначения: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Единственная очередь и текущий указатель: https://github.com/markmalina/automations/issues/14
Продукт #1 и S1 #9 остаются открытыми.

## Окно и организация

Новое поручение08.11 supersedes прежний cutoff00:30. Работа разрешена08.11 до08:00 Europe/Moscow. Последний worker обязан иметь terminal receipt и cleanup не позднее07:50. После08:00 никаких действий. К07:35 нельзя назначать реализацию без доказанного бюджета на сохранение и очистку до07:50.

Обновлены и повторно проверены enabled/schedule/prompt существующих собственных автоматизаций:
- Контроллер: Automation_45158fef76248191b075a7e96d9665f0; DTSTART08.11 00:25 Europe/Moscow, HOURLY COUNT8; последнее назначенное время07:25.
- Исполнитель: Automation_303e1627b4e48191b93deb79a403c290; DTSTART08.11 00:35 Europe/Moscow, HOURLY COUNT8; последнее07:35.
- Итог: Automation_ddc69faaf3748191aa5ae702a125b786; однократно08.11 07:55 Europe/Moscow. Прежний итог00:25 перенесён.

Это запланированные исполнения, не подтверждение будущего запуска или доставки. Новые расписания не создавать. Соседние расписания не менять. При полной реальной приёмке либо окончании окна остановить только указанные собственные ночные циклы. Финальный отчёт не подменяет cleanup.

Контроллер за<=8мин читает свежие указатель, текущую issue, новые claims/PR/checks/jobs/terminal receipts; принимает факты или возвращает одно конкретное исправление в той же issue. Не реализует за worker. Source PR можно merge только после review/checks с exact expected head и readback. Это не deployment.
Worker берёт только одну явно READY задачу; до эффекта claim с execution/time/source/branch в task, затем RUNNING в#14. При RUNNING/unknown effect второго writer нет; время истечения claim не доказывает terminal. Не вводить framework leases.
Обычный worker<=25мин total, implementation<=20мин, >=5мин на сохранение/cleanup. Последний запуск имеет всего15мин. Один bounded outcome/branch/PR, без merge/закрытия issue; терминальный REVIEW с exact head/checks/evidence/остатком. Исправления reuse issue; новый outcome — новая issue. После terminal receipt закончить execution.

## Проверенный baseline

PR25 https://github.com/markmalina/automations/pull/25 принят и объединён.
Exact accepted head: 0dace85be4055adb23e4e9a748ca6c627cbcb47a.
Merge/current code baseline: 592a235e9beb9925837c1e754b6f9f29758a91d1.
Восемь файлов после merge прочитаны и blob SHA совпали. Bootstrap embedding синхронизирован; bytes вне декларации payload сохранены.
CI42413073458 attempt1 job128525165555 success:67 Node+78 Python PASS; actual job14с. Известный subtotal двух jobs0.5167 runner-min не является полным историческим итогом. Денежная оценка/provider usage/invoice неизвестны, не ноль; вести прежний ledger без обнуления.
#24/#17/#21 приняты и закрыты как source/local outcomes. #10/#12/#13/#15 тоже приняты. Не повторять их проверки без изменившегося основания.
Native2.46.6 synthetic2-file+sameUUID replay PASS: независимые bytes/size/SHA256/Gitblob;1commit/1ref/0protocolerrors; обе executions success exact publishedVersion3d37f383-5a7c-44c6-991c-151bab7fb79e. Это loopback GitHub stub, не realGitHub/live acceptance.
У пользователя ещё нет доказанного работающего постоянного сервиса и полного Work→n8n→realGitHub маршрута. Source/localstub/CI/merge не равны deploy/live.

## Приоритет работы и критерии результата

1. Каждый controller проверяет только новые ответы case19384733 в подтверждённой Gmail thread1a1b5a93ee17df00, sender support@openai.com. Фактический ответ на новый конкретный диагностический вопрос в том же case разрешён; без секретов/спама/повторения неизменного запроса. На00:18 новых ответов после13:58/нашего14:44 нет. Письмо «изучаем» не является исправлением admission.
2. Если доказано устранение причины прежнего Railway refusal или применимый штатный admission, приоритет следующей READY task — существующий S1#9. Перечитать свежий native snapshot/effective-node/grant criteria, работать только existing target. Затем первая полезная реальная S2 выгрузка с commitURL и независимым remote bytes readback по exactSHA.
3. После первой реальной выгрузки — непокрытые live S3 пакет100files/30MB/требуемые3цикла, recovery/idempotency/negative cases, назначения в разрешённые репозитории и повтор из нового обычного Work согласно фактическим критериям#1/#9. Суточную стабильность не объявлять по восьмичасовому окну.
4. Пока admission не установлен, единственный первый независимый outcome: #26 https://github.com/markmalina/automations/issues/26 — native100files/30,000,000bytes+sameUUID replay через настоящий локальный n8n2.46.6 и synthetic GitHub stub. Все100bytes/size/SHA256/Gitblob независимо;1commit/ref,2success exactversion,0protocolerrors. Это новый mass native case, не liveS3. Scope/установка/бюджет/cleanup заданы в issue; production candidate не расширять.
5. После#26 controller назначает только действительно новый нужный source/recovery/negative/native outcome по наблюдаемому gap. Не плодить audits прежнего blocker, повторные installs/неизменные CI/фиктивные commits ради видимости почасового прогресса. Если все полезные действия blocked — WAITING_EXTERNAL с точной фазой, кодом, evidence, зависимостью и готовой задачей продолжения.

## Непереходимые границы

Прежний original Railway accept_deploy отклонён. Не повторять его ради диагностики и не обходить через UI/CLI/Ops. Общее ночное разрешение не отменяет отказ. READ-only diagnostics могут уточнить admission, write для диагностики запрещён. При требовании недоступного auth/approval — точный WAITING_EXTERNAL package. Без новых ресурсов, RAM/CPU, подписки, credentials или permissions.
Не менять Gate/Ops/data/соседние проекты и их автоматизации. Старый failedID, журнал и pending сохранить.
Публичный репозиторий не получает реальные bytes/grants/headers/PEM/DB/private payload/сырые логи. Использовать безопасный allowlist evidence. Не использовать новый uploadId/UUID для обхода неизвестного эффекта или отказа.
Нужные сохранения — n8n при разрешённом доступном пути, иначе GitHub connector; после записи exactcontent/head readback и commit link.
Строго разделять source facts, CI, merge, deployment, native fixture и реальную пользовательскую приёмку. Неизвестные расходы/метрики обозначать unknown.

## Очистка и checkpoint

Старый cache /workspace/scratch/d3cab9545dca/task17-public-npm-cache удалён07.11 23:50:20МСК, отсутствие проверено дважды; outstanding oldcache=NONE. Старый native runtime/DB/keys/grants/processes очищен. Не предполагать cache существующим.
Новый собственный cache разрешён только с публичными registry bytes/metadata без auth/cookies, абсолютным path/bytes/contents/deadline<=07:50 в task и#14. Иначе удалить. Все runtime/DB/keys/grants/fixtures/rawlogs/node_modules/processes stop+wait/cleanup перед terminal. Последний исполнитель cleanup<=07:50; final проверяет реальные pointers, не чужие каталоги.
Каждый материальный checkpoint#14 содержит QUEUE_STATE, TASK_URL, source/head, фактический результат, next owner, owncache pointers и cleanup. Единственный авторитет — GitHub receipts и реальные runs, не воображаемая связь со старым чатом.
Финал07:55: что стало доступно пользователю, что принято, links/CI/merge/deploy/live отдельно, активные операции/cleanup, оставшийся точный blocker и следующий ответственный. Полный результат не обещан при внешнем admission blocker; его отсутствие сообщить прямо.

ДАЛЬШЕ: исполнитель — принять единственную READY#26; контроллер — проверить её фактический результат и новый штатный допуск для#9.
