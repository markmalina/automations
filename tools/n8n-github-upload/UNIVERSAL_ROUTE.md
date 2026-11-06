# Work → n8n → любой репозиторий markmalina

Статус 07.11.2026: рассмотренный исходник, **не установленный и не принятый
живой сервис**. Прежний запуск Railway снова отменён инструментом даже после
явно выбранного режима «чтение разрешено, изменения с подтверждением».
Эквивалентный deploy через browser/CLI/Ops не выполняется.

## Что меняется для Work

Поручение владельца определяет репозиторий, существующую ветку и назначение
файлов. Work использует прежнее OAuth-подключение n8n и workflow
`workUploadGrantPilot`. Новый постоянный token, пароль, отдельный Work или
ручная сборка workflow для каждой выгрузки не нужны.

1. Прочитать актуальный published grant workflow через существующее подключение.
2. Клиентом `work_upload.py prepare` подготовить manifest и локальный bundle.
   В manifest только пути, размеры, SHA-256 и точные repoId/repository/branch/prefix.
   Байты файлов не проходят через модель.
3. Execute существующего grant workflow получает `bundle.grantRequest` как
   metadata. Из execution читать только `Return temporary grant` программно;
   значение короткого grant не печатать.
4. Передать JSON grant в `receive-grant` через проверенный stdin-механизм и
   сохранить0600. Подробности текущего exec/PTY механизма в `WORK_CLIENT.md`.
5. `work_upload.py upload` передаёт исходные байты напрямую по HTTPS multipart
   на единственный закреплённый n8n URL. После ответа Work читает exact GitHub
   commit и сверяет каждый файл, используя имеющееся GitHub-подключение.
6. При потере ответа сохранять тот же uploadId/manifest. Состояния uncertain
   и committed-but-unpublished не сбрасывать новым ID; использовать квитанцию
   и отдельное восстановление. Короткий grant после использования удалить.

Все операции делает исполнитель. Эти пункты не являются поручением владельцу
создавать файлы, workflow или переносить секреты руками.

## Как n8n сохраняет пакет

Новый binary workflow `workOwnerRepositoryUploadV1` использует штатные узлы
n8n, существующий App JWT credential и GitHub Git Data API. Полная история
репозитория и рабочая копия не клонируются. Байты, размер и SHA проверяются
до GitHub-запросов; grant связан с точным target и digest. Короткий GitHub
installation token ограничен одним repoId и contents:write, затем проверяются
полное имя и неизменяемый ownerId23397294.

GitHub blob API требует внутреннего Base64: это автоматическое преобразование
внутри n8n. Передача Work → n8n остаётся бинарным multipart; ZIP и Base64 через
модель не используются. Создаются blob/tree и один commit. Commit SHA сохраняется
в SQLite **до** обновления ветки; ref обновляется только force:false, затем
проверяется достижимость именно этого commit. Повтор не создаёт второй commit.

Для transient grant в ExecuteCommand передаётся только SHA-256, не raw token.
Legacy raw protocol и универсальный hash protocol разделены: V2 grant не может
попасть в старый обработчик с фиксированным freelance-назначением.

## Совместимость и эксплуатационные границы

- Старые uploads/failed ID `9d94bcf3-9a28-4014-93d5-ce8e5d259c7d`, grants,
  receipts и состояния сохраняются. Миграция добавляет nullable target_json,
  не пересоздаёт журнал. Snapshot учитывает новую привязку и нормализует null
  на прежней схеме, поэтому можно проверить сохранение строк при миграции.
- Прежний grant ID/OAuth scopes/credential references сохранены. Bootstrap
  импортирует и публикует оба фиксированных workflow штатным n8n CLI до запуска
  публичного процесса. Ошибка import/publish прерывает startup и удаляет
  временный workflow-файл. Новых постоянных секретов нет.
- Persistent child ограничен одной production execution на данном upload
  instance; blob HTTP nodes дополнительно идут по одному с интервалом1с.
  Binary workflow timeout300с, client socket timeout300с.100file batch требует
  более100с только на pacing; фактическая скорость API/сети ещё не измерена.
- До100файлов, суммарно32,000,000байт, manifest≤30,000UTF-16codeunits,
  POSIX/NFC пути≤2048UTF-8байт и≤255байт на компонент. Запрещены traversal,
  .git, control/backslash/comma и конфликты имён/файл-каталог.
- Ветка должна существовать; режим файлов100644. Создание PR/ветки и запись
  `.github/workflows` не заявляются этим contents-only маршрутом. Защита веток
  не отключается. Изменение App permissions требует отдельного конкретного
  действия, если оно действительно понадобится.
- Сохранение execution data binary workflow выключено; это **не доказательство**
  своевременной очистки нативных binary temp-файлов n8n. Диск, память, queue,
  невалидные запросы и pruning должны пройти живую приёмку.

## Что проверено и что остаётся

Локально проверены CLI/PTY binary transport, SQLite migration/grant/target,
legacy/concurrent claims, реальные Code snippets, graph, source reproducibility,
stock CLI import/publish ordering и cross-component Python → SQLite → n8n Code.
Независимая проверка закрыла несовпадение field grammar, cross-endpoint target
bypass, FIFO blocking, raw grant argv и неавтономный generator.

Настоящий n8n engine/API импорт и выполнение, OAuth из нового Work,100файлов/
30МБ через сервер, memory/disk/pruning, restart и сохранность live journal
**не проверены**. MCP SDK/best-practices tools возвращали Internal error;
параметры узлов сверялись по первичным исходникам установленного n8n@2.46.6.
Прогоны Code snippets не заменяют native workflow validation.

Этот исходник не меняет STAGED patch, не включает Ops mutation releases и не
снимает прежний отказ допуска. Пока требуется закончить допустимый Ops writer,
принять конкретный runtime source/patch и пройти исходный механизм запуска.
После этого одна общая live-приёмка закрывает пользовательский маршрут.

Задачи: https://github.com/markmalina/ops/issues/434 и
https://github.com/markmalina/automations/issues/1 .
Правила: https://github.com/markmalina/ai/blob/main/WORK-RULES.md .
