# Troubleshooting

Все сообщения в консоли начинаются с времени (`YYYY-MM-dd HH:mm:ss`). Полные traceback пишутся в `logs/`.

## [FAIL] KiCad executable not found

Установите KiCad 10 (`winget install --id KiCad.KiCad --exact`) или задайте в `.env`:

```
KICAD_EXE=C:\Program Files\KiCad\10.0\bin\kicad.exe
KICAD_CLI=C:\Program Files\KiCad\10.0\bin\kicad-cli.exe
KICAD_SYMBOL_DIR=C:\Program Files\KiCad\10.0\share\kicad\symbols
```

## MCP не появляется в Cursor

1. Workspace = `C:\Cursor_Projects\MCP_KiCad`.
2. Включите сервер `kicad` в MCP settings и перезапустите MCP (Disable → Enable) или перезагрузите Cursor.
3. `.cursor/mcp.json` должен запускать `.venv/Scripts/python.exe -m kicad_ai.mcp.server` (не `uv run`, если Cursor не видит tools).
4. Зависимости: `mcp>=1.10,<2` и `fastmcp>=2.6,<3`. **MCP 2.x / FastMCP 4.x** ломают tool discovery в Cursor.
5. Ручной тест:
   ```powershell
   uv run doctor
   .\.venv\Scripts\python.exe tools\validation\test_mcp_stdio.py
   ```
   Ожидается `OK tools/list: 35 tools`.

## ERC / DRC / BOM не запускаются

Нужен `kicad-cli`. Схему нужно **сохранить** на диск до `run_erc` / `validate_project`. Если схемы открыты в GUI, возможны `.lck` — MCP предупредит, но не будет делать вид, что всё чисто.

Нет `.kicad_pcb` — DRC возвращает `SKIPPED`, это не ошибка CLI и не успешная проверка платы. `render_pcb` / `render_pcb_3d` в том же случае тоже SKIPPED, без фейковой картинки. У примера mcp-test плата есть (`mcp-test.kicad_pcb`); у `projects/oxy/oxy` её нет — там DRC по-прежнему SKIPPED.

## Render пустой / старый

Источник — `kicad-cli`, не AI. PNG схемы получается из SVG KiCad. Если схема изменилась, hash в `renders/<project>/schematic/full.meta.json` не совпадёт и рендер пересоберётся (`--force` принудительно). Каталог `renders/` в gitignore.

3D: `kicad-cli pcb render`. Нет модели у компонента — WARNING в отчёте, не ERROR.

## SKiDL не находит символы

Нужны переменные `KICAD10_SYMBOL_DIR` / `KICAD_SYMBOL_DIR` (их выставляет `kicad_ai.detect.require_kicad`). Каталог лабораторного кода — `skidl_lab/`, не `skidl/` (иначе перекрывается пакет PyPI).

## Схема не открывается в KiCad 10

После save выполняется `kicad-cli sch upgrade`. Если файл всё равно старый, откройте его в GUI один раз и сохраните, либо пришлите лог `sch upgrade`.

## search_symbols пустой

Запрос ищет подстроку в имени символа официальных `.kicad_sym`. Пример: `Fuse`, `R-78E`, `LED`, `+12V`. Не выдумывайте MPN, которого нет в библиотеке.

## PermissionError / PathDenied

Путь вне whitelist. Запись: `projects/`, `backups/`, `logs/`, `docs/`, `components/`, `skidl_lab/`. SKiDL netlist — только `skidl_lab/generated/`.

## Python 3.14

Системный Python 3.14 не используется. Проект фиксирует 3.12:

```powershell
uv sync
uv run python --version
```
