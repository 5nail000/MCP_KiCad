# Architecture

## Выбранный стек

- **KiCad 10.0.6** — GUI, официальные symbol/footprint libraries, `kicad-cli`.
- **kicad-sch-api 0.5.6** — чтение/запись `.kicad_sch`, компоненты, провода, labels, pin discovery, connectivity.
- **kicad-ai MCP** — FastMCP поверх библиотеки: whitelist, backup, логи, create_project, ERC/DRC/BOM.
- **SKiDL 2.3.0** — опциональный Python-слой (блоки, тестовые цепи, SKiDL ERC). Не владеет файлами проекта.
- **Python 3.12** через `uv` (классификаторы kicad-sch-api заканчиваются на 3.12; системный 3.14 не используем).

Файловый workflow: KiCad GUI **не обязан** быть запущен. Скрипт `open-kicad` открывает проект для визуальной проверки.

- **kicad-sch-api pin numbers vs KiCad 10** for some rotated symbols (e.g. `Device:Fuse` at 90°) can disagree. Electrical connectivity is taken from `kicad-cli sch export netlist`, not from `get_net_for_pin` (that API currently raises `TypeError: unhashable type: 'Net'` on these files).

## Источник истины

```text
                 ┌────────────────────┐
                 │      KiCad         │
                 │ authoritative      │
                 │ schematic / PCB    │
                 │ projects/**        │
                 └─────────┬──────────┘
                           │
                    validation
                           │
              ┌────────────┴────────────┐
              │                         │
        ERC / DRC                 Python tests
        kicad-cli                 pytest + SKiDL ERC
              │                         │
              └────────────┬────────────┘
                           │
                     PASS / FAIL

skidl_lab/
  ├── reusable circuit blocks
  ├── generated test netlists (only skidl_lab/generated/)
  ├── connectivity experiments
  └── engineering validation
```

Каталог лабораторного слоя — `skidl_lab/`, не `skidl/`: имя `skidl` занято пакетом PyPI.

SKiDL **не** пишет `.kicad_sch` в `projects/`. Две расходящиеся схемы одного проекта запрещены.

Существующие проекты остаются в `projects/examples/` и `projects/user/` (не переносились в отдельный `kicad/`).

## Почему не stock `kicad-sch-mcp`

Встроенный MCP пакета принимает любой абсолютный путь в `load_schematic` / `save_schematic`. Это несовместимо с требованием «только workspace». Мы используем ту же библиотеку, но со своим сервером.

## Отклонённые варианты

- **kicad-mcp-pro** — слишком широкий набор tools, не нужен для schematic-first среды.
- **Seeed kicad-mcp-server** — силён в анализе PCB; можно рассмотреть позже для `pcbnew`.
- **kicad-mcp-kipy** — требует запущенный KiCad 10 IPC; плохо для headless/smoke.
- Вендорить git-клон kicad-sch-api — незачем, пакет на PyPI.

## Не реализовано сейчас (не имитировать)

- Генерация PCB / раскладка (MCP этого не делает; тестовая плата mcp-test собрана скриптом pcbnew)
- Gerber / Pick & Place / IPC-2581
- SPICE
- LCSC / JLCPCB / автоподбор MPN
- Скачивание PDF datasheet с сайтов производителей
- Автоматический `generate_schematic` из SKiDL в файлы KiCad-проекта
- Blender / Diffusion / screenshot-GUI для рендера

Рендер схемы/платы: настоящий `kicad-cli sch export svg|pdf`, `pcb export svg`, `pcb render` (3D PNG). PNG схемы — растеризация **KiCad SVG** (PyMuPDF), не генерация картинки. Нет `.kicad_pcb` → PCB/3D = **SKIPPED**.

Интерфейс на будущее: `Renderer` / `KiCadRenderer` / заготовки `BlenderRenderer` и `AIRenderer` (не подключены).

DRC: настоящий `kicad-cli pcb drc`. Нет `.kicad_pcb` → статус **SKIPPED** с причиной, не PASS. У `projects/examples/mcp-test` есть тестовая плата для smoke DRC/render (не production).

## Безопасность

Запись разрешена только в `projects/`, `backups/`, `logs/`, `docs/`, `components/`, `skidl_lab/`, `renders/`. Path traversal и пути вне workspace → `PathDenied`.

SKiDL netlist — только `skidl_lab/generated/`. Путь в `projects/` или расширение `.kicad_sch` → отказ.

`remove_component` требует `confirm=true`.

## Логи

`logs/kicad-ai-YYYYMMDD.log` — timestamp, operation, project, tool, error, traceback.
