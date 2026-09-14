# Workflow

## Новый проект

1. `create_project(name, location="user")` → `.kicad_pro` + `.kicad_sch` + library tables.
2. `search_symbols` / `get_symbol_info` — только реальные lib_id.
3. `add_component` / `add_power_symbol` на сетке 1.27 мм.
4. `get_component_pins` → `connect_pins` / `add_wire` / `add_label` / `add_junction`.
5. `save_schematic` (backup, если файл уже был).
6. `inspect_connectivity` + `run_erc`.
7. Сообщить ошибки, не прятать traceback.

## Изменение существующего проекта

1. Прочитать схему и connectivity.
2. Предложить изменение пользователю (кратко).
3. Backup → modify → save → validate.
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

Схема — инженерный артефакт:

```powershell
git status
git diff
git add projects/user/<name>
```

Коммит создавайте только когда пользователь явно просит. `commit-message.txt` в `.gitignore` — для пушей по правилу репозитория.
