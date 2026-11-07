# S2.A / №10 — проверка контроллера PR11

07.11.2026, 14:02 МСК.
Задача: https://github.com/markmalina/automations/issues/10
PR: https://github.com/markmalina/automations/pull/11
Проверенный head: 8098cfcfe131d4f43bd1f469f429bd78eecfda76
Регламент: https://github.com/markmalina/ai/blob/main/WORK-RULES.md

## Решение

**CHANGES REQUESTED: одно исправление R1.** S2.A пока не принят; PR11 не объединён, №10 остаётся открытой. Новая issue и новый Work для этого исправления не нужны.

Проверен весь diff пяти файлов: verifier, code-mode bridge, инструкция, тесты и отчёт.
GitHub CI42365732052 действительно completed/success, attempt1 на указанном head. Логи job128383266794 подтверждают Node66 PASS, Python60 PASS; повтор hosted CI контроллер не запускал.
https://github.com/markmalina/automations/actions/runs/42365732052

Сравнение деревьев base ad155965a73b4f4e768d7323112c46f32127ebf3 и head подтверждает ровно пять заявленных изменений. work_upload.py, server bootstrap/ledger, оба workflow, генераторы и S1 candidate не изменены.

Контроллер прочитал exact-commit traversal, binding bundle/receipt, проверку remote bytes/SHA256/Git blob, обработку ошибок, ограничения и protected stdin bridge. Содержательного нарушения exact-commit проверки в этом проходе не найдено. Это ограниченное review, не утверждение отсутствия всех дефектов.

Новый набор Python-тестов воспроизведён. На локальном снимке с лишним завершающим переводом строки первоначальный общий прогон дал 19 PASS + один PTY timeout; отдельный и последующие прогоны прошли. После приведения локальных копий к точным bytes PR SHA256 четырёх исполняемых/тестовых файлов совпали с таблицей исполнителя; обычный прогон этих exact bytes: 20 PASS. Детерминированный сценарий R1 на exact bytes затем снова дал FAIL. Различие вариантов локального снимка не скрывается.

Публичный smoke README/JPG прочитан в сохранённом отчёте исполнителя; заново контроллер его не запускал. Приватный доступ, масштаб ответа и n8n upload/S2 live этим review не подтверждены.

## R1 — ложный timeout в тестовом reader

Место:
https://github.com/markmalina/automations/blob/8098cfcfe131d4f43bd1f469f429bd78eecfda76/tools/n8n-github-upload/test_work_readback.py#L231-L247

run_cli создаёт Popen(stdout=PIPE) с обычным буферизованным reader. Перед каждым readline он делает select.select([process.stdout], ..., 3). Первый readline может заранее прочитать READY_FOR_GRANT и следующий READBACK_REQUEST в Python-буфер. На следующей итерации ОС-дескриптор уже пуст, select возвращает timeout, хотя следующая строка готова в reader.

Независимая минимальная демонстрация:
```python
import os, select
rd, wr = os.pipe()
os.write(wr, b"READY_FOR_GRANT\nREADBACK_REQUEST {}\n")
stream = os.fdopen(rd, "rb")
stream.readline()
assert not select.select([stream], [], [], 0)[0]
assert stream.readline() == b"READBACK_REQUEST {}\n"
stream.close()
os.close(wr)
```

Реальный exact-head тест воспроизведён без изменения product/helper/test source: обёртка первого вызова select.select в процессе теста делает time.sleep(0.3), затем вызывает исходный select. Это обычное допустимое позднее планирование читателя, позволяющее обеим стартовым строкам накопиться в pipe. Запуск только test_cli_pty_actual_protocol_restores_modes_and_no_echo завершается за 3.320s:
`AssertionError: [] is not true : protocol deadline`, строка246, exit1.

Следовательно, это подтверждённый дефект test harness, а не установленный сбой verifier или защищённого транспорта. Обычный PASS не исключает его.

### Требуемая дельта

1. Исправить reader в run_cli, чтобы ожидание учитывало уже полученные строки: например, неблокирующее/небуферизованное чтение с собственным ограниченным line buffer. Сохранить настоящие deadline и cleanup. Не заменять это увеличением timeout, sleep в основном тесте, retries или удалением проверки.
2. Добавить детерминированный regression для READY + REQUEST в одном доступном блоке и для частичной строки. Сохранить canary/no-echo/termios/0600 проверки и предел ожидания.
3. Пройти относящиеся локальные проверки и полный discovery; один необходимый CI на исправленном head. Не перезапускать старый зелёный run.
4. Обновить тот же PR11/отчёт №10, проверить remote bytes/head и передать контроллеру. Не объединять, issue оставить открытой.

Не менять verifier/bridge/server только ради этого тестового исправления без конкретного связанного дефекта. S1/Railway/n8n остаются вне scope. Не начинать следующую самостоятельную задачу.

## Статус исполнения

Проверки контроллера завершены; запущенные локальные test processes завершились. Deploy, n8n grant/upload/replay, изменения permissions или данных не выполнялись. Ответ поддержки в этом ходе не проверялся. Исполнитель ещё не принял это исправление; фоновой межчатовой доставки нет.

ДАЛЬШЕ: исполнитель — исправить R1 в том же PR11 по №10; контроллер — проверить новый head после передачи результата.
