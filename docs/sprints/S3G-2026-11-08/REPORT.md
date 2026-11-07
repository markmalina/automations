# #30 — native invalid grant denial

08.11.2026 02:46 МСК. Готово к приёмке контроллером.
Task: https://github.com/markmalina/automations/issues/30
Queue: https://github.com/markmalina/automations/issues/14
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Baseline6c2525cf46f1de8fc00ac788ecbf9148ddd25c06.
Execution worker-20261107T233917Z-d3cab9545dca.

## Результат

**PASS_NEGATIVE, ожидаемый отказ, не успешная выгрузка.**
В fresh локальном n8n2.46.6 отправлен один настоящий multipart binary POST реальным work_upload.upload:2synthetic files/282bytes. У свежего fakegrant изменён один hex символ token; token остался64hex, manifest/target/digest/expiry не менялись. Client grant_valid не обходился/не менялся.
Получен E_UPLOAD_HTTP_500. Сам по себе HTTP500 не считается PASS: native warn/error log независимо подтвердил allowlisted GRANT_DENIED, а before-stop metadata содержит ровно execution1/status error/workflowVersionId eed21dad-05d4-43c5-9e10-7a5e912b0fbe.
Перед POST active/published версия и nodes snapshot точно совпали с ожидаемой test-only копией: та же eed21dad-05d4-43c5-9e10-7a5e912b0fbe.
Общий счётчик stub на входе любого HTTP handler:
requests0/commitWrites0/refWrites0/protocolErrors0, включая installation token requests.
Read-only ledger до/после: uploadRows0/commits0/receipts0/states{}. Новая uploadclaim/confirmedreceipt не создана.
Все эти критерии проверены совместно. Rawlogs/headers/grants/DB не опубликованы. Metadata lastNode/errorCode null: подробные данные не дали пригодного node/error поля; GRANT_DENIED получен из native log строгим regex, точный lastNode не утверждается.
Corrected-grant запросов, replay/restart, новых UUID после отказа, positive/mass повторов и realGitHub операций не было. Native whole cycle35.215s, внешний timeout360s не сработал. Source/local/stub negativePASS не deployment/live. Product#1/S1#9 OPEN.

## Source и проверки

Изменены только existing native_binary_probe.py,5guard tests test_native_denial.py и report.
Новый --invalid-grant допускается только с small fixture без restart. До единственного POST читаются безопасные ledger counters, изменяется один символ fake token; реальный uploader выполняет все свои проверки.
Общий fixture.requests увеличивается до protocol parsing, чтобы обнаружить даже installation-token HTTP.
Expected-denial ветка никогда не исполняет positive replay. После before-stop extraction отрицательная приёмка требует1error execution exactversion,servercodeGRANT_DENIED,clientHTTP4xx/5xx,всеstubcounters0 и неизменный пустой ledger. Положительные small/mass/restart checks сохранены.
5tests предотвращают false positives: complete expected evidence; HTTP500 alone/missing native execution; installationtoken request при0writes; staleversion; changed ledger/receipt.
Local90Python PASS;67Node+bootstrapfixture/syntax PASS. HostedCI exacthead/run/job/logs фиксируются в terminal receipt отдельно; CI не выполняет actualnativecase.

Production client/ledger/ownerworkflow/grantworkflow byte hashes совпали с baseline. Local bootstrap оказался старой копией доPR25; первая Node проверка это обнаружила. Он перематериализован exactmain2b7639972d5a9b6e5948f567c10d612b4abe153f, затем относящаяся Node проверка прошла. Python green не повторялся. Production source вGitHub не менялся.
Unchanged blobSHA:
work_upload.py3b687bdf78afe4b5471cc92f240fc4e95dc728e5;
upload-ledger.cjs98b8a2179a36c7543b25f19df2f3515cd6dee94a;
ownerworkflow45fb5ed95c9bfc8e4819f1719cc2278004c39830;
grantworkflowfda4b735c20480fefb5b92e51d23f9052033cad5;
bootstrap2b7639972d5a9b6e5948f567c10d612b4abe153f.
Стандартные6test-only substitutions:2GitHuborigins/3ledgerpaths/1fakecredentialname. Graph/settings/credentials/permissions/productiontimeout/CI unchanged.

Reproduce в fresh own0700 root с pinned node_modules и source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json,native_binary_probe.py}:
python source/native_binary_probe.py --root OWN_ROOT --invalid-grant
Runtime/keys/DB/privatefixtures/rawlogs нужно удалить после safe metadata extraction; helper finally останавливает и ожидает свои процессы.

## Среда и обнаруженное расхождение filesystem

На входе текущий night08-public-npm-cache отсутствовал, а ранее удалённый task17-public-npm-cache вновь оказался виден. Это расхождение с historical confirmed-deletion receipt, а не доказанная причина восстановления/сбоя платформы. Причина неизвестна; старые receipts не переписаны.
Старый cache НЕ использовался. Текущая собственная копия проверена:4010publicindexrecords,onlyregistry.npmjs.org,zeroauth/cookie/userinfo,1,304,853,488filebytes; удалена в этом execution, absence проверено.
Одна разрешённая обычная ONLINE install (без prefer-offline, т.к. новыйcache отсутствовал), exactn8n@2.46.6/ignore-scripts/save-exact/no-audit/no-fund, explicitownnightcache; exit0. Proxy/CA/TLS сохранены. Никаких offline-first/secondfullinstall/systempackages/Docker/daemon/policy/credentials changes.
n8n/nodes/CLI2.46.6,Node24.22.1. Official integrity совпал:
sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==.
Lockv3/2372entries SHA256f560de2944fa8c03a4ef0c146bde6cc7230e5462bb2cc95c8c3e773b88d1a372.
SQLiteinitialbindingmissing; одна Debugnode-gypbuild2jobs<=180s exit0,actualrequire3.44.2. Official Nodeheaders24.22.1 SHA256322e0a27db9088093ab8347bdc8c7e0aaa21dc9ed548390bf06b394494c09267 совпал сSHASUMS.
Setup закончился02:45, within12мин; полныйworkerlimit25мин включаетsavecleanup.

## Cleanup / pointers / ограничения

Native processesStopped=true; install/build/test/probe commands terminal через toolhandles/Popenwait/finally.
Дополнительная process enumeration через ps UNAVAILABLE (fatal library error, lookup self). Пустой вывод не считается независимым processcount0. Собственные новые процессы останавливались по реально сохранённым handles/processgroups и wait.
Own task30 root/runtime/DB/PEM/grants/fixtures/rawlogs/node_modules/headers/temp source удаляется доterminal; absence в receipt.
Публичный новый cache проверен послеinstall:
 /workspace/scratch/d3cab9545dca/night08-public-npm-cache
1,421,951,584filebytes/4055indexrecords,onlyregistry.npmjs.org,zeroauth/cookie/userinfo,retainedonly_cacache. Adjunctlogs/notifier удалены.
DEADLINE08.11 07:50МСК; carrypointer в#14 до verified deletion. Не утверждать crossWorkavailability/cachecompleteness.
RSS remains UNAVAILABLE из прежней#26, не измерялся/не выдаётсязаzero/Railwaycapacity.
Previous knownpartial CI ledger1.6167runner-min переносится; новыеrun/job/timing вterminal. Monetaryestimate/providerusage/invoiceunknown.
Railway/S1/live n8n/RAM/CPU/подписка/permissions/credentials/oldfailedID/journal/pending/Gate/Ops/data/neighbors/automations untouched. Originalaccept_deploy не повторялся/не обходился; supportworkerне трогал. Publicrepo не получает реальныеbytes/grants/headers/PEM/DB/privatepayload.
ДАЛЬШЕ: контроллер — принять expecteddenial evidence/PR exacthead/checks либо вернуть конкретныйgap в#30; исполнитель неmerge/не закрываетissue.
