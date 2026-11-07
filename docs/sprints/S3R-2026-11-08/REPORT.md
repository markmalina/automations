# #28 — native receipt recovery after n8n restart

08.11.2026 01:39 МСК. Готово к приёмке контроллером.
Task: https://github.com/markmalina/automations/issues/28
Queue: https://github.com/markmalina/automations/issues/14
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Baseline:1280fc1b3e7fa12a989ad183900db71110226b4b.
Execution:worker-20261107T223530Z-d3cab9545dca.

## Результат и граница

**PASS:** один малый synthetic bundle2files/282bytes, один initial POST и ровно один replay того же UUID/grant после настоящего stop+wait/start n8n2.46.6. Удалённые stub bytes/size/SHA256/Gitblob проверены до остановки и после replay;2/2 совпали. После restart возвращён тот же commit, replayed=true. Всего commitWrites1/refWrites1/protocolErrors0.
Это новый restart boundary; массовый100files/30MB #26 не повторялся. Никаких realGitHub/Railway/live операций. Product#1/S1#9 остаются pending.

До stop first execution success и version d5de46fb-f075-429e-a042-6d7916dd2afd. Проверен подтверждённый ledger receipt и соответствие его commit исходному receipt.
n8n process group получил TERM, leader wait завершён, отсутствие старой группы проверено killpg(pid,0) с bounded ожиданием; oldProcessWaited/oldProcessGroupAbsent=true. Новый процесс имеет другой PID; restartProcessChanged=true.
Те же DB/ledger/runtime/encryption env сохранены, import/publish/owner setup между этими двумя запросами не выполнялись. Inode n8n DB не изменился. Stub и его head/objects сохранялись в памяти.
Readiness после restart дополнен повторным чтением active/published version и точного nodes snapshot: та же d5de46fb-f075-429e-a042-6d7916dd2afd, restartPublishedNodesExact=true.
Ledger read-only evidence до/после restart:
- state confirmed, inode3426706;
- receipt SHA2568b9c42e6afdc76efa5ed4864896a1f1d0ed712efe90dccbda78cd832455eaea7;
- synthetic commit SHA a707714f120aebc2902ea97230c3aee5c0445adb.
Все эти поля совпали. Содержимое receipt/DB/grant не публиковалось.
После replay две native executions id1/id2 success, обе workflowVersionId той же версии. Metadata прочитаны перед финальным stop; lastNode/errorCode null, lastNode не заявляется подтверждённым.
Первый request1.562s; весь native cycle32.620s, внешний timeout360s не сработал. RSS не измерялся повторно: ограничение #26 остаётся UNAVAILABLE, не zero/не Railway capacity PASS.

## Изменения и проверки

Только existing native_binary_probe.py,4новых локальных guards в test_native_restart.py и данный report.
Добавлен --restart-before-replay только для small fixture. Default small/mass без flag сохраняют прежний порядок. Существующий snapshot check выделен в published_snapshot с сохранением active/published equality и exactnodes; при restart дополнительно запрещена смена версии.
ledger_evidence использует SQLite mode=ro и проверяет state/commit/receipt, возвращает только hash/commit/inode. Перед restart проверяются исходные bytes,commit/ref/errors,firstexecution success; после — DB inode,ledger evidence,snapshot,далее единственный replay. Deadlineguard перед replay сохранён, production timeout не менялся.
Guard tests: reject changed version; reject changed nodes при той же версии; reject missing durable receipt; detect changed receipt fingerprint.
Local67Node+85Python PASS, bootstrapfixture/syntax PASS. Hosted CI фиксируется отдельно в terminal receipt и не подменяет actual native recovery.

Production source byte hashes сверены с baseline и не изменены:
work_upload.py3b687bdf78afe4b5471cc92f240fc4e95dc728e5;
upload-ledger.cjs98b8a2179a36c7543b25f19df2f3515cd6dee94a;
ownerworkflow45fb5ed95c9bfc8e4819f1719cc2278004c39830;
grantworkflowfda4b735c20480fefb5b92e51d23f9052033cad5;
bootstrap2b7639972d5a9b6e5948f567c10d612b4abe153f.
Native test-only export substitutions те же6: GitHub origins2,ledger absolute paths3,fakeJWTcredentialname1. Graph/settings/permissions/grant logic unchanged.

Reproduce в fresh own0700 root с pinned node_modules и source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json,native_binary_probe.py}:
python source/native_binary_probe.py --root OWN_ROOT --restart-before-replay
Оператор удаляет приватный runtime/DB/keys/grants/fixtures/rawlogs/node_modules после безопасного evidence extraction. Процессы helper останавливает finally.

## Среда, cleanup, расходы

Одна ONLINE --prefer-offline exactn8n@2.46.6 --ignore-scripts --save-exact --no-audit --no-fund install с проверенным собственным publiccache; exit0. n8n/nodes/CLI2.46.6,Node24.22.1.
Official n8n integrity verified:
sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==.
Lockv3/2372entries SHA256c18cdb6fe72c68e42f80d7dec21cfe2f161faf6e07f7722b38328273bbd57619.
Missing SQLite binding → одна Debugnode-gypbuild2jobs<=180s,exit0/actualrequireSQLite3.44.2. Official24.22.1headers SHA256322e0a27db9088093ab8347bdc8c7e0aaa21dc9ed548390bf06b394494c09267 matches officialSHASUMS.
Setup в пределах12мин, полный worker budget25мин включает save/cleanup. No systempackages/Docker/daemon/networkpolicy/credentials changes.

Nativehelper processesStopped=true. Own task28 prefix с runtime/DB/PEM/grants/privatefixtures/logs/headers/node_modules/source copies удаляется до terminal; absence/process check фиксируется в receipt.
Publiccache re-audit:
 /workspace/scratch/d3cab9545dca/night08-public-npm-cache
1,342,582,118filebytes;4052indexrecords;onlyregistry.npmjs.org;zero nonempty auth/cookie fields/userinfo; retained only_cacache. Logs/notifieradjuncts removed.
DEADLINE08.11 07:50МСК. Carry pointer в#14 до confirmed deletion. Старыйtask17cache absent/not recreated. Cache completeness/crossWorkavailability не гарантируется.
Предыдущий известный partial CI ledger1.0000runner-minute переносится. Новый CIrun/job/timing в terminal; monetaryestimate/providerusage/invoice unknown, не ноль.

Original Railwayaccept_deploy не повторён/не обойдён; Railway/S1/live n8n/permissions/resources/oldfailedID/journal/pending/Gate/Ops/data/neighborautomations untouched. No real bytes/DB/PEM/grants/headers/privatepayload в publicrepo.
ДАЛЬШЕ: контроллер — review exact PR/head/checks и принять native recovery; при admission продолжить#9, иначе определить только реальный следующий gap. Исполнитель не merge/не закрываетissue.
