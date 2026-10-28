# Работа с Visual Paradigm MCP

## Назначение

Этот репозиторий предоставляет stdio MCP для открытого проекта Visual Paradigm Desktop. Работайте с моделью через MCP и официальный Java OpenAPI. Не редактируйте `.vpp` как SQLite/XML, не вызывайте Python-handlers и IPC напрямую, не подменяйте недостающие инструменты разовыми Java jobs.

Если операции не хватает, добавьте общий инструмент с параметрами. Не зашивайте названия, пути и ID конкретных пользовательских диаграмм в исходники.

## Архитектура и файлы

```text
MCP client
  → initialize / notifications/initialized / tools/list / tools/call
  → mcp_server.py: схемы, валидация, dispatch
  → transport.py: однопоточный локальный IPC с блокировкой
  → src/local/codex/Bridge.java: выполнение на Swing EDT внутри VP
  → jobs/Command.class: общий dispatcher из src/operations/Command.java
  → открытая модель Visual Paradigm
```

- `mcp_server.py` — публичная точка запуска MCP-сервера.
- `mcp_client.mjs` — стандартный Node-клиент stdio MCP, без прямого доступа к IPC.
- `transport.py` — внутренний транспорт сервера, не агентский интерфейс.
- `plugin/plugin.xml` — манифест плагина; VP предоставляет `openapi.jar` самостоятельно.
- `scripts/build.py` — компиляция плагина и dispatcher с `--release 11`, затем атомарная замена `.class`.
- `scripts/install.py` — установка и резервная копия старого плагина; не перезапускает VP.
- `tests/test_*.py` — офлайн-проверки, не обращаются к пользовательскому проекту.
- `ipc/`, `exports/`, `backups/`, `jobs/`, `plugin/classes/` — локальные/генерируемые данные, исключены из Git.

Сеть не используется. Транспорт зависит от POSIX `fcntl`; Windows не поддерживается. Один bridge root нельзя делить между несколькими процессами VP.

## Установка и подключение

Полная инструкция: [README.md](README.md). Кратко:

```sh
python3 scripts/build.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/install.py --plugin-dir '/path/to/VP/plugins'
```

До установки/обновления пользователь должен сохранить работу и закрыть VP. Не закрывайте приложение с несохранённой работой ради настройки. Для замены установленного плагина используйте `--replace`: прежняя версия попадёт в `backups/installed-plugin-*`.

Установщик записывает `bridge.properties` с абсолютным путём к этому репозиторию. Если каталог переместили, переустановите плагин и исправьте путь MCP entrypoint. `VP_HOME`/`--vp-home` выбирают VP для сборки; `JAVAC` — компилятор. `VP_MCP_PYTHON` выбирает Python для Node-клиента. `VP_MCP_ROOT` задаёт корень транспорта сервера, но не меняет конфигурацию плагина. Для VP JVM есть явное переопределение `-Dvp.mcp.root=...`.

После запуска VP зарегистрируйте `python3 /absolute/path/to/mcp_server.py` как stdio MCP. Убедитесь, что клиент действительно загрузил инструменты. Регистрация записи в конфигурации сама по себе этого не доказывает. Если встроенные инструменты не появились, используйте комплектный клиент:

```sh
node mcp_client.mjs list
node mcp_client.mjs call get_project '{}'
node mcp_client.mjs call list_diagrams '{}'
```

Он проходит `initialize` → `notifications/initialized` → `tools/list` → `tools/call`. Запуск Python-сервера этим клиентом является нормальной частью MCP.

Изменения `Command.java` требуют сборки, но не рестарта VP: dispatcher загружается заново для каждой команды. Изменения `Bridge.java` требуют установки и рестарта. Изменения Python-сервера требуют нового MCP-подключения; CLI-клиент создаёт его при запуске.

Проверено: сборка Java 11 bytecode, офлайн-тесты и операции с Use Case/Activity на VP Community Edition 18.1 macOS. Чистую установку из нового клона нужно отдельно проверить в VP; не выдавайте компиляцию за успешную установку или проверку всех операций.

## Рабочий порядок

1. Прочитайте `get_project`: имя файла, `modified`, активная диаграмма. Не переключайте и не сохраняйте пользовательский проект ради настройки или офлайн-тестов.
2. Получите `list_diagrams`, затем `get_diagram`. Берите настоящие ID из чтения, не полагайтесь на старые сообщения.
3. Для анализа/предложения не меняйте модель. При разрешённой существенной правке создайте `backup_project`, учитывая, что он сохраняет все текущие изменения пользователя.
4. Выполняйте только разрешённые изменения. Не запрашивайте повторное согласование уже разрешённого действия.
5. Перечитайте результат, проверьте связанные представления и экспорт PNG. После разрешённой правки сохраните проект и проверьте `modified:false`.

Примеры — замените ID результатами чтения:

```sh
node mcp_client.mjs call get_diagram '{"diagram_id":"DIAGRAM_ID"}'
node mcp_client.mjs call connect_elements '{"diagram_id":"DIAGRAM_ID","model_type":"Include","from_id":"BASE_SHAPE_ID","to_id":"INCLUDED_SHAPE_ID"}'
node mcp_client.mjs call rename_element '{"diagram_id":"DIAGRAM_ID","element_id":"SHAPE_ID","name":"Новое имя"}'
node mcp_client.mjs call set_bounds '{"diagram_id":"DIAGRAM_ID","element_id":"SHAPE_ID","x":100,"y":200,"width":240,"height":60}'
node mcp_client.mjs call get_connector '{"diagram_id":"DIAGRAM_ID","element_id":"CONNECTOR_ID"}'
node mcp_client.mjs call save_project '{}'
node mcp_client.mjs call export_diagram '{"diagram_id":"DIAGRAM_ID","filename":"review-unique.png"}'
```

### Модель, представление и условия

- `element_id` — фигура/линия на диаграмме; `model_id` — общий объект модели. `rename_element` меняет общую модель, `set_bounds` — одну фигуру. Они обновляют раскладку подписи.
- Создавайте нативные `Include`/`Extend`, не `Dependency` с похожим текстом. Include: базовый → включаемый; Extend: расширяющий → базовый.
- `condition` задаёт семантическое условие Extend или guard потока. `set_flow_guard` меняет guard существующего ControlFlow/ActivityObjectFlow и очищает прежнее имя-подпись. `get_connector` возвращает guard.
- `set_object_type` задаёт текстовый тип ObjectNode, не переименовывая прежний классификатор; ссылка на него заменяется.
- Точки расширения use case пока не редактируются отдельным инструментом. При необходимости добавьте его; не имитируйте семантику надписью.
- `delete_relationship` удаляет только связь с единственным представлением. `delete_disconnected_node` требует отсутствия любых связей, дочерних моделей, поддиаграмм и других представлений. Сначала явно удалите разрешённые связи.
- `model_type` соответствует фабрике OpenAPI. Совместимость всех типов с любой диаграммой не гарантируется.

### Геометрия

`createConnector(Point[])` на проверенной версии мог смещать точки и оставлять нулевой размер подписи. После создания прочитайте `get_connector`, установите `set_connector_points`, при необходимости `set_connector_caption`, затем снова прочитайте и экспортируйте.

Координаты задаются в системе диаграммы. `set_connector_points` сбрасывает раскладку подписи, поэтому положение подписи задавайте после маршрута. VP может округлять координаты на единицу. Проверяйте стрелки, подписи, границы дорожек, отсутствие обрезанного текста и непреднамеренных правок других диаграмм. Сохранение не подтверждает корректность модели.

`set_connector_style` со `style:"rectilinear"` задаёт нативный маршрут с прямыми углами; `"oblique"` возвращает свободный стиль. `get_connector` возвращает `connector_style`. Прямые углы не выравнивают блоки и точки подключения по общей оси: для вертикальной цепочки отдельно проверьте центры блоков и координаты всех стрелок.

## Таймауты и ошибки

`isError:true` — ошибка, не успех. `ipc/ready.json` может быть устаревшим; работоспособность доказывает ответ MCP. Таймаут оставляет `ipc/inflight.json` с ID запроса, ответ появляется в `ipc/<ID>.json`.

**Не повторяйте запись автоматически.** Операция могла выполниться. Прочитайте ответ и проверьте состояние модели. Не удаляйте pending/inflight, пока выполнение не завершено или не остановлено и результат не выяснен. Если результат неизвестен, остановите зависимые записи и сообщите пользователю. Частичная ошибка не откатывается вызовом `save_project`.

Данные IPC/экспортов/резервных копий могут содержать весь проект и локальные пути. Не коммитьте и не отправляйте их без отдельного разрешения. Не распространяйте `openapi.jar` из установки VP.

## Расширение MCP

1. Найдите метод в официальном OpenAPI и проверьте установленный `openapi.jar` через `javap`.
2. Добавьте параметризованный инструмент в `mcp_server.py`: JSON Schema, валидация до мутации, честные readOnly/destructive аннотации.
3. Добавьте общий case в `src/operations/Command.java`. Сохраните контракт ошибок, учитывайте общие модели и возможность частичной мутации.
4. Добавьте целевую офлайн-проверку. Выполните сборку и тесты.
5. Проверьте инструмент через MCP. Read-only smoke допустим на пользовательском проекте; запись тестируйте только в разрешённом объёме или на явно разрешённой disposable-модели. Не запускайте прямой Python handler.

## Официальные справочники

- [Visual Paradigm OpenAPI guide](https://circle.visual-paradigm.com/docs/open-api/)
- [JavaDoc OpenAPI](https://www.visual-paradigm.com/support/documents/pluginjavadoc/)
- [Установка плагина](https://circle.visual-paradigm.com/docs/open-api/installing-plug-in/installing-a-visual-paradigm-plug-in/)
- [Turning points API](https://knowhow.visual-paradigm.com/openapi/turning-pts-api/)
