# #32 — native recovery after lost response

08.11.2026 03:43 МСК. Готово к приёмке контроллером.
Task: https://github.com/markmalina/automations/issues/32
Queue: https://github.com/markmalina/automations/issues/14
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Baseline1cd7e3a9499d0252de98bea52ae591dbc1d9c9e4.
Execution worker-20261108T003706Z-d3cab9545dca.

## Фактический результат

**PASS:** реальный work_upload.upload отправил первый multipart binaryPOST через настоящий локальный n8n2.46.6. Test-only HTTPConnection adapter получил HTTP200headers, не читал/не парсил receiptbody, закрыл соединение и поднял ConnectionResetError. Реальныйclient вернул E_UPLOAD_OUTCOME_UNKNOWN. Faultcount1/headersStatus200/bodyNotRead=true.
Это намеренная локальная fault injection; реальной аварии Railway/внешней сети не утверждаем. Байты могли уже находиться в сетевых буферах; applicationreceiptbody не читался и клиенту не возвращался.

Перед любым повтором read-only подтверждены совместно:
- firstexecution terminalsuccess, version fa82a391-21f3-4c62-8770-d3ae446d0f13;
- stubcommit/ref1/1/errors0, оба удалённых synthetic файла2/2 (282bytes) независимо совпали по bytes/size/SHA256/Gitblob;
- ledger state confirmed, receipt exists, commit совпал сstubhead.
Authoritative evidence сохранено ДО replay, replayAuthorizedAfterTerminal=true. Не слепой retry и не второй writer.

Затем ровноодин обычный replay техже bundle/UUID/grant (adapter выключен) вернул receipt/replayed=true/тотже commit. Всего1commit/1refwrite,0protocolerrors;13stubHTTPrequests включая проверочныеreads/token, не13writes. Ledgerreceipt/state/commit/inode совпали до/после:
receiptSHA256697de564bf082b81c630ee3f52cfe5f18a6ed39efd3ef91385eee10ce3051cd6;
syntheticcommitSHA1ff1357df4f211d61cfe2b4b0076e44f483a209a;
inode3704858.
Обаblobbytes/size/SHA256/Gitblob повторно проверены послеreplay.
Nativeexecutions id1/id2 обеsuccess, обеworkflowVersionId fa82a391-21f3-4c62-8770-d3ae446d0f13. Before-stopmetadata; lastNode/errorCode null, точныйlastNode не заявляем.
Published active/version/nodesexact проверены доfirstPOST;6стандартныхtest-only substitutions origins2/ledgerpaths3/fakecredentialname1.
Полныйnativecycle49.767s. ПолеfirstRequestSeconds1.890s включает также authoritativeread-only checks, не является чистым network latency. Внешний360s timeout не сработал.
НовыхUUID/grants, restart, mass/negative повторов, realGitHub/Railway/live операций не было. Localstub/fault/recoveryPASS не deploy/live; Product#1/S1#9 остаютсяpending.

## Source scope и проверки

Только existing native_binary_probe.py,3adapterregressions test_native_response_loss.py и данныйreport.
Добавлен --lose-first-response толькоsmall, mutuallyexclusive сrestart/invalidgrant. Adapter наследует штатныйHTTPConnection, все send/request действия делегируются; fault толькопосле настоящего200getresponse и доbodyread. HTTP!=200 возвращается штатномуclient безмаскировки. FirstUNKNOWN не даёт автоматическийreplay: strictfirstterminal/version/remote bytes/ledgerchecks, затемобычныйsameUUIDreplay и неизменныйreceipt/commit. Positive small/mass/restart иnegative checks сохранены.
Tests:200body не читается;503не скрывается;faultcount не больше1. Фактический clientUNKNOWN иnative recovery проверены отдельно настоящим runtime, а не замененыэтимиunit tests.
Local67Node+93Python PASS, bootstrapfixture/syntaxPASS. Hosted CI exacthead/run/job/logs вterminalreceipt; hostedCI не исполняет этотnativecase.

Production source exactbaseline blobSHA:
work_upload.py3b687bdf78afe4b5471cc92f240fc4e95dc728e5;
upload-ledger.cjs98b8a2179a36c7543b25f19df2f3515cd6dee94a;
ownerworkflow45fb5ed95c9bfc8e4819f1719cc2278004c39830;
grantworkflowfda4b735c20480fefb5b92e51d23f9052033cad5;
bootstrap2b7639972d5a9b6e5948f567c10d612b4abe153f.
Этиproduction файлы/CI/settings/grants/permissions не менялись. Publishednodes exact относится к test-only origin/path/name copy, не live service.

Воспроизведение в fresh own0700root с pinned node_modules и source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json,native_binary_probe.py}:
python source/native_binary_probe.py --root OWN_ROOT --lose-first-response
Runtime/DB/keys/grants/fixtures/rawlogs/node_modules удалить после safeevidenceextraction; helperfinally stop+wait своих процессов.

## Среда, cleanup, cache, расходы

Одна разрешённая ONLINEprefer-offline exactn8n@2.46.6 ignore-scripts/save-exact/no-audit/no-fund install с existing explicitownpubliccache, exit0. n8n/nodes/CLI2.46.6/Node24.22.1; officialintegrityverified:
sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==.
Lockv3/2372entries SHA2566844c157ca50b0b9a915c4125d0dd0caa782538e06773d8b3499913040e3f7f4.
SQLiteinitialbindingmissing→однаDebugnode-gypbuild2jobs<=180s exit0,actualrequire3.44.2; official24.22.1headers SHA256322e0a27db9088093ab8347bdc8c7e0aaa21dc9ed548390bf06b394494c09267 matchesSHASUMS.
Setup завершён03:42, within12мин. Inheritedproxy/CA/TLS, nooffline-first/secondinstall/systempackages/daemon/Docker/policy/credentials changes.
Current filesystem был согласован сlastreceipt:nightcacheexists,oldtask17cacheabsent; sourcecopies заново сверены сmain, bootstrapактуален. Не предполагалась доступность по истории без проверки.

Native processesStopped=true, outercommand terminal; дополнительная ps enumeration в этомexecution доступна и показалаownnativeprocesscount0. Это свежее наблюдение; прежняя#30psUNAVAILABLE не переписывается.
Own task32prefix/runtime/DB/PEM/grants/privatefixtures/rawlogs/node_modules/headers/temphelpers/sourcecopies удаляются доhandoff; absence вterminalreceipt.
Cache re-audit:
 /workspace/scratch/d3cab9545dca/night08-public-npm-cache
1,472,316,187filebytes/4016indexrecords,onlyregistry.npmjs.org,zeroauth/cookie/userinfo,only_cacache; adjunctlogs/notifier удалены.
DEADLINE08.11 07:50МСК; carrypointer в#14 доverifieddeletion. Completeness/crossWorkavailability не гарантированы. Oldtask17cacheabsent.
RSS остаётся прежнимUNAVAILABLE, не измерялся заново/не zero/Railwaycapacity.
PreviousknownpartialCIledger2.1667runner-min переносится; новыйrun/job/timing вterminal. Monetaryestimate/providerusage/invoiceunknown.

Railway/S1/live n8n/RAM/CPU/subscription/permissions/credentials/oldfailedID/journal/pending/Gate/Ops/data/neighborprojects/automations untouched. Originalaccept_deploy не повторялся/не обходился; supportworkerне трогал. Publicrepo не получает реальныеbytes/grants/headers/PEM/DB/privatepayload/rawlogs.
ДАЛЬШЕ: контроллер — review exactPR/head/checks и принять native response-loss recovery либо вернуть одинgap в#32; оценить реальныеоставшиесяS1/live blockers. Workerнеmerge/не закрываетissue.
