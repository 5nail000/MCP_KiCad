# Architecture

## Выбранный стек

- **KiCad 10.0.6** — GUI, официальные symbol/footprint libraries, `kicad-cli`.
- **kicad-sch-api 0.5.6** — чтение/запись `.kicad_sch`, компоненты, провода, labels, pin discovery, connectivity.
- **kicad-ai MCP** — FastMCP поверх библиотеки: whitelist, backup, логи, create_project, ERC/BOM.
- **Python 3.12** через `uv` (классификаторы kicad-sch-api заканчиваются на 3.12; системный 3.14 не используем).

Файловый workflow: KiCad GUI **не обязан** быть запущен. Скрипт `open-kicad` открывает проект для визуальной проверки.

- **kicad-sch-api pin numbers vs KiCad 10** for some rotated symbols (e.g. `Device:Fuse` at 90°) can disagree. Electrical connectivity is taken from `kicad-cli sch export netlist`, not from `get_net_for_pin` (that API currently raises `TypeError: unhashable type: 'Net'` on these files).


## Почему не stock `kicad-sch-mcp`

Встроенный MCP пакета принимает любой абсолютный путь в `load_schematic` / `save_schematic`. Это несовместимо с требованием «только workspace». Мы используем ту же библиотеку, но со своим сервером.

## Отклонённые варианты

- **kicad-mcp-pro** — слишком широкий набор tools, не нужен для schematic-first среды.
- **Seeed kicad-mcp-server** — силён в анализе PCB; можно рассмотреть позже для DRC/`pcbnew`.
- **kicad-mcp-kipy** — требует запущенный KiCad 10 IPC; плохо для headless/smoke.
- Вендорить git-клон kicad-sch-api — незачем, пакет на PyPI.

## Не реализовано сейчас (не имитировать)

- Генерация PCB / раскладка
- DRC
- Gerber / Pick & Place / IPC-2581
- SPICE
- LCSC / JLCPCB / автоподбор MPN
- Скачивание PDF datasheet с сайтов производителей

Точки расширения: `tools/validation`, `tools/conversion`, `tools/project`.

## Безопасность

Запись разрешена только в `projects/`, `backups/`, `logs/`, `docs/`, `components/`. Path traversal и пути вне workspace → `PathDenied`.

`remove_component` требует `confirm=true`.

## Логи

`logs/kicad-ai-YYYYMMDD.log` — timestamp, operation, project, tool, error, traceback.
