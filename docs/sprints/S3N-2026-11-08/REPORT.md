# #26 — native100files/30MB PASS

08.11.2026 00:39МСК. Готово к приёмке контроллером.
Task: https://github.com/markmalina/automations/issues/26
Queue: https://github.com/markmalina/automations/issues/14
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Execution: worker-20261107T213315Z-d3cab9545dca.
Baseline main: e9a71b8183b0139a2b4d09a3b53857e7be298b88.

## Что проверено

Один новый synthetic пакет ровно100файлов по300000bytes =30,000,000bytes через настоящий Work client→локальный n8n2.46.6→loopbackGitHubstub. Содержимое детерминированное бинарное, один Unicodepath,100различных SHA256. Без ZIP/текстового преобразования; multipart binary на входе n8n, GitHub API base64 только внутри workflow/stub.

PASS100/100: каждый удалённый stubblob независимо сравнен с исходными bytes, размером и SHA256 manifest, пересчитан Git blob SHA. Затем ровно один replay того же bundle/UUID/grant: тот же receiptcommit, replayed=true. Stub commitWrites=1/refWrites=1/protocolErrors=0.
Это не реальный GitHub, не liveS3, не три цикла, не доказательство работоспособности постоянного сервиса. Продукт#1/S1#9 остаются незавершёнными.

Actual publishedVersion94c611f9-53f7-460d-a177-2c607454535d; active/published IDs совпали, publishednodes exact ожидаемой test-only копии. Native executions id1/id2 обе success и workflowVersionId равен этой версии; metadata прочитаны доstop. lastNode/errorCode null, lastNode здесь не утверждается.
Test-only substitutions ровно6: GitHub origin в Prepare upload и installationendpoint,3ledgerabsolute paths, fakeJWTcredentialname. Production graph/settings/limits/permissions не менялись.
Первый upload103.510s; полный probe128.445s, внешнее измерение128.614s. Within360s bound; test-only connectionfactory300s, productiontimeouts не менялись.

## Source scope и воспроизведение

Изменён только native_binary_probe.py: option --case mass-100-30mb; defaultsmall сохраняет прежние2filebytes. Stub требует точные payloads,100paths/tree entries дляmasscase; прежние strict commit/ref/replay/versionchecks не ослаблены. Test-only HTTPtimeout300s толькоmasscase; budgetguard передreplay.
Добавлены3regressions: точный100/30MB boundary+uniqueSHA+Unicode/binary; unchanged smallbytes; unknowncase rejection.
Нужны isolated own0700 root с pinned node_modules и source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json,native_binary_probe.py}.
Команда: python source/native_binary_probe.py --root OWN_ROOT --case mass-100-30mb.
Внешняя обёртка ограничивала processgroup360s сTERM/wait/KILL fallback, nativehelper finally stop+wait. После получения безопасных evidence оператор удаляет runtime/DB/keys/grants/fixtures/rawlogs/node_modules.

Точные неизменные production blobSHA сверены с currentmain:
- work_upload.py3b687bdf78afe4b5471cc92f240fc4e95dc728e5
- upload-ledger.cjs98b8a2179a36c7543b25f19df2f3515cd6dee94a
- ownerworkflow45fb5ed95c9bfc8e4819f1719cc2278004c39830
- grantworkflowfda4b735c20480fefb5b92e51d23f9052033cad5
- bootstrap2b7639972d5a9b6e5948f567c10d612b4abe153f

Локально81Python PASS; exactCI Node command67PASS+bootstrapfixture/syntaxPASS. Дополнительный fullNodeglob99PASS не прибавляется к67 как уникальныеtests. HostedCI и exacthead фиксируются в terminalreceipt отдельно; hostedCI не запускает этот externalnativecase.

## Подготовка среды

Одна разрешённая ONLINE npm install exactn8n@2.46.6, ignore-scripts/no-audit/no-fund, explicitowncache, inheritedproxy/CA/TLS. Exit0; n8n/n8n-nodes-base/CLI2.46.6; node24.22.1.
Official n8nintegrity совпал: sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==.
Lockv3/2372entries SHA256d000e2d1cea44d6444e950ee2fb12afdaf3c5e20e55be557364b0e4e678341d9.
InitialSQLitebindingmissing; одна разрешённая Debugnode-gypbuild2jobs<=180s exit0, actualrequireSQLite3.44.2.
OfficialNode24.22.1headers SHA256322e0a27db9088093ab8347bdc8c7e0aaa21dc9ed548390bf06b394494c09267 совпал сofficialSHASUMS.
Setup completed00:37, within12minbudget. No systempackages/daemon/Docker/newcredentials/networkpolicychange.

## Локальные ресурсы и ограничения измерения

Sampled runtime disk peak144,877,492bytes (du-sb с интервалом1s; это sampled maximum, не доказанный instantaneouspeak). Установка+headers+runtime на одном замере2,173,583,604bytes. Publicnpmcache отдельно1,278,759,249filebytes.
PeakRSS UNAVAILABLE: сборщик /proc не получил пригодных RSS samples (нулевой агрегат). Ноль НЕ объявляется потреблением памяти; nativecase ради метрики не повторялся. Сравнение с лимитами Railway0.5vCPU/1GB не выполнено.
Измерения относятся только к данной local среде, не Railway capacityacceptance.

## Cleanup и следующий шаг

Nativehelper processesStopped=true; собственных n8nprocesses0 послеterminal. Private runtime/DB/PEM/grants/fixtures/rawlogs/node_modules/headers удаляются доhandoff сabsencecheck вterminalreceipt.
Publiccache retained:
 /workspace/scratch/d3cab9545dca/night08-public-npm-cache
1,278,759,249filebytes;4056indexrecords;onlyregistry.npmjs.org;zero nonempty auth/cookie fields/userinfo. Только_cacache, logs/notifieradjuncts удалены.
DEADLINE08.11 07:50МСК; carrypointer в#14 доconfirmeddeletion. Старыйtask17-public-npm-cache не восстанавливался.
CIcostledger: предыдущий известныйsubtotal0.5167runner-min переносится; новыеrun/job/timing/estimate вterminalreceipt. Providerusage/invoice/денежнаяоценка unknown.
Railway/S1/live n8n/oldfailedID/journal/pending/neighborprojects/automations untouched. Originalaccept_deploy не повторён/необойдён; support не менялся. Реальныхpayload/headers/grants/PEM/DB/logs вpublicrepo нет.

ДАЛЬШЕ: контроллер — принять100/100 nativeevidence иsourcePR; определить следующий реальный gap или продолжение#9 при доказанном admission. Не merge/не закрывать этуissue исполнителем.
