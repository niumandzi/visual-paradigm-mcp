# Visual Paradigm MCP

Локальный MCP-сервер для чтения и редактирования открытого проекта Visual Paradigm Desktop через официальный Java OpenAPI. Изменяются нативные модели и фигуры; файл `.vpp` сохраняет сам Visual Paradigm.

```text
MCP-клиент → Python stdio-сервер → локальный IPC → Java-плагин → VP OpenAPI
```

OpenAPI работает внутри процесса VP, поэтому Java-плагин нужен как мост. Сетевой порт не открывается. Сторонние Python/npm-пакеты не требуются.

## Требования

- Visual Paradigm Desktop с `lib/openapi.jar` — JAR не включён в репозиторий.
- Python 3.9+, JDK 11+ с `javac`.
- Node.js 18+ — только для комплектного тестового MCP-клиента.
- macOS/POSIX: транспорт использует `fcntl`. Поддержка Windows не реализована.

Проверено на Visual Paradigm Community Edition 18.1 на macOS. Сборка и офлайн-тесты проверяются отдельно от установки плагина; работа из нового чистого клона после установки требует проверки в VP.

## Установка

1. Клонируйте репозиторий в постоянный каталог. Для стандартной установки VP на macOS:

   ```sh
   python3 scripts/build.py
   python3 -m unittest discover -s tests -p 'test_*.py' -v
   ```

   Если VP установлен иначе, задайте каталог, содержащий `lib/openapi.jar`:

   ```sh
   python3 scripts/build.py --vp-home '/path/to/visual-paradigm/app'
   ```

   Компилятор можно выбрать переменной `JAVAC`. Сборка создаёт Java 11 bytecode, не меняет установленный плагин и проекты.

2. Сохраните работу и закройте VP. Узнайте каталог плагинов через **Help → Install Plugin → ручное копирование → Copy Path**. На macOS:

   ```sh
   python3 scripts/install.py --plugin-dir "$HOME/Library/Application Support/VisualParadigm/plugins"
   ```

   При обновлении добавьте `--replace`: установщик сначала скопирует прежний плагин в `backups/`. Скрипт не закрывает VP и не сохраняет проект автоматически.

3. Запустите VP и откройте проект. Зарегистрируйте stdio MCP-сервер в своём клиенте, указав **абсолютные пути**:

   ```json
   {
     "mcpServers": {
       "visual_paradigm": {
         "command": "/absolute/path/to/python3",
         "args": ["/absolute/path/to/visual-paradigm-mcp/mcp_server.py"]
       }
     }
   }
   ```

   Синтаксис внешней конфигурации зависит от MCP-клиента. Сервер использует stdio JSON-RPC, не HTTP.

4. Проверьте протокол и доступ к открытому проекту:

   ```sh
   node mcp_client.mjs list
   node mcp_client.mjs call get_project '{}'
   node mcp_client.mjs call list_diagrams '{}'
   ```

   `list` работает без VP; чтение проекта требует запущенного плагина. `VP_MCP_PYTHON` выбирает Python для комплектного Node-клиента.

## Возможности

19 инструментов:

| Задача | Инструменты |
| --- | --- |
| Чтение | `get_project`, `list_diagrams`, `get_diagram`, `get_connector` |
| Создание | `create_diagram`, `create_element`, `connect_elements` |
| Редактирование | `rename_element`, `set_bounds`, `set_object_type`, `set_flow_guard` |
| Геометрия связей | `set_connector_points`, `set_connector_style`, `set_connector_caption` |
| Удаление | `delete_relationship`, `delete_disconnected_node` |
| Файлы | `export_diagram`, `save_project`, `backup_project` |

Схемы параметров доступны через `tools/list`. Проверенные сценарии — Use Case и Activity; совместимость всех типов элементов OpenAPI со всеми диаграммами не заявляется.

## Важное поведение

- Правки остаются в открытом проекте до `save_project`. Сохранение включает также несохранённую работу пользователя.
- `backup_project` сначала сохраняет весь проект, затем копирует `.vpp`. Не вызывайте его для задачи только на чтение.
- Имя меняется у общей модели во всех её представлениях; координаты — у одной фигуры.
- Удаление общей связи запрещено. Удаление узла разрешено только после явного удаления его связей, при отсутствии дочерних моделей и других представлений.
- После таймаута не повторяйте запись: операция могла выполниться. Проверьте ответ и модель. Один bridge root рассчитан на один экземпляр VP.
- IPC, экспорты и резервные копии могут содержать данные проекта. Они исключены из Git; не публикуйте их.

Подробный рабочий порядок, расширение MCP и официальные справочники: **[AGENTS.md](AGENTS.md)**.
