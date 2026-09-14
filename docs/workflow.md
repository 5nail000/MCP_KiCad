# Workflow

## Новый проект

1. `create_project(name, location="user")` → `.kicad_pro` + `.kicad_sch` + library tables.
2. `search_symbols` / `get_symbol_info` — только реальные lib_id.
3. `add_component` / `add_power_symbol` на сетке 1.27 мм.
4. `get_component_pins` → `connect_pins` / `add_wire` / `add_label` / `add_junction`.
5. `save_schematic` (backup, если файл уже был).
6. `inspect_connectivity` + `validate_project` (ERC обязателен; DRC если есть PCB).
7. Сообщить ошибки, не прятать traceback. Не выдавай DRC SKIPPED за PASS.

## Изменение существующего проекта

1. Прочитать схему и connectivity.
2. Предложить изменение пользователю (кратко).
3. Backup → modify → save → `validate_project`.
4. Не переименовывать refdes и net names без причины.
5. Summary diff: что добавлено/удалено, какие цепи затронуты.

## Соединения

| Механизм | Это электрическое соединение? |
|---|---|
| Провод, концы на пинах/проводах | Да |
| Junction в точке T | Да (обязателен для T) |
| Net label с тем же текстом | Да (логическая цепь) |
| Power symbol (`power:GND`) | Да (глобальная цепь по имени) |
| Два провода просто пересеклись | **Нет** |

## Git

Каталог `projects/` в `.gitignore`: схемы и платы остаются локально, в репозиторий не коммитятся. Примеры создайте через `uv run kicad-ai example` или MCP `create_project`.

```powershell
git status
git diff
```

Коммит создавайте только когда пользователь явно просит. `commit-message.txt` в `.gitignore` — для пушей по правилу репозитория.

## SKiDL

SKiDL живёт в `skidl_lab/`. Не генерируй из него `.kicad_sch` поверх `projects/`. Netlist только в `skidl_lab/generated/`. Блок `rail_12v_5v` повторяет *архитектуру* mcp-test для экспериментов, но mcp-test в KiCad остаётся единственной схемой этого примера. Тестовая плата `projects/examples/mcp-test/mcp-test.kicad_pcb` — smoke DRC/render, не плата на производство.
