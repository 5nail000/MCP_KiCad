# KiCad AI — локальная среда Cursor → MCP → KiCad

## 1. What is this?

Рабочая среда для **AI-assisted engineering** в KiCad: LLM через MCP создаёт и правит **настоящие** `.kicad_sch` / `.kicad_pro`, проверяет связность, гоняет ERC и BOM через официальный `kicad-cli`.

Это не генератор картинок и не mock. Схему можно открыть в KiCad 10.

## 2. Architecture

```
Cursor Agent  --stdio MCP-->  kicad-ai (whitelist + backup + logs)
                                |                         |
                                v                         v
                         kicad-sch-api 0.5.6          kicad-cli 10.0.6
                                |                         |
                                +-----> projects/** <-----+
```

- Schematic engine: пакет [`kicad-sch-api`](https://pypi.org/project/kicad-sch-api/) (реальный S-expression parser/writer).
- ERC / BOM / netlist / `sch upgrade`: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`.
- Stock `kicad-sch-mcp` **не** подключён напрямую: у него нет whitelist путей.

Отклонённые альтернативы и будущие слои: [docs/architecture.md](docs/architecture.md).

## 3. Requirements

Проверено на этой машине:

- Windows 10 x64
- KiCad **10.0.6** (`C:\Program Files\KiCad\10.0\`)
- Python **3.12** через uv (системный 3.14 не используется)
- uv 0.12.x
- Git

## 4. Installation

В PowerShell из корня репозитория:

```powershell
cd C:\Cursor_Projects\MCP_KiCad
.\scripts\setup.ps1
```

Эквивалент вручную:

```powershell
uv sync --group dev
uv run doctor
```

## 5. Configuration

Скопируйте `.env.example` в `.env` только если автоопределение KiCad не сработало.

Переменные:

- `KICAD_AI_WORKSPACE` — корень workspace (Cursor задаёт сам)
- `KICAD_EXE`, `KICAD_CLI`, `KICAD_SYMBOL_DIR`, `KICAD_FOOTPRINT_DIR` — ручные пути
- `KICAD_AI_BACKUP_KEEP` — сколько backup хранить (по умолчанию 10)
- `KICAD_AI_LOG_LEVEL` — `INFO` / `DEBUG`

## 6. Cursor MCP setup

Файл [`.cursor/mcp.json`](.cursor/mcp.json) запускает `.venv/Scripts/python.exe -m kicad_ai.mcp.server` (быстрее и совместимо с Cursor; MCP 1.x).

1. Откройте этот folder как workspace Cursor.
2. Cursor Settings → MCP → включите сервер `kicad`.
3. Подтвердите tools.
4. Проверка: `uv run doctor` должен показать `[OK] MCP configuration`.

Ручной запуск (обычно не нужен):

```powershell
uv run start-mcp
.\scripts\start-mcp.ps1
```

## 7. Creating first project

Скажите агенту:

> Создай проект контроллера насоса в projects/user/pump-controller

Агент должен вызвать `create_project`, затем добавлять символы из библиотек KiCad, соединять пины, сохранить, прогнать ERC.

Пример из репозитория:

```powershell
uv run kicad-ai example
```

создаёт `projects/examples/mcp-test/` (12V → предохранитель → R-78E5.0-0.5 → 5V + LED).

## 8. Working with existing projects

1. `list_projects` / `load_schematic`
2. `get_schematic_info` + `inspect_connectivity`
3. Предложить изменение
4. `save_schematic` (backup создаётся автоматически)
5. `run_erc`
6. Показать summary

Проекты пользователя кладите в `projects/user/`. Не пишите вне workspace: MCP это запретит.

## 9. Backup and rollback

Перед перезаписью существующей схемы MCP копирует проект в `backups/<name>/YYYY-MM-DD_HHMMSS/`. Старые копии чистятся (последние 10).

```powershell
.\scripts\backup-project.ps1 projects\examples\mcp-test
uv run kicad-ai backup projects\examples\mcp-test
```

Откат: tool `restore_backup` или копирование папки backup обратно в project dir.

## 10. Validation

```powershell
uv run doctor
uv run pytest tests/test_smoke.py -v
.\scripts\open-kicad.ps1
```

Doctor проверяет KiCad, Python 3.12, uv, Git, kicad-sch-api, `.cursor/mcp.json`, workspace.

## 11. Troubleshooting

См. [docs/troubleshooting.md](docs/troubleshooting.md). Логи: `logs/kicad-ai-YYYYMMDD.log` (каждая строка начинается с времени). Traceback не скрывается.

## 12. Example prompts for LLM

1. Создай проект `projects/user/pump-controller` с входом 12V, предохранителем и DC-DC 5V.
2. Прочитай `projects/examples/mcp-test` и перечисли компоненты и цепи.
3. Добавь в mcp-test конденсатор 100nF на выход 5V, сохрани backup и покажи connectivity.
4. Найди в библиотеках KiCad символ предохранителя, не создавай новый.
5. Соедини выход U1 с net `VOUT_5V` через label, не считая пересечение проводов соединением.
6. Прогони ERC по текущей схеме и объясни каждое нарушение.
7. Сгенерируй BOM CSV для mcp-test.
8. Добавь защиту от обратной полярности (диод) на вход 12V, не меняя существующие reference.
9. Покажи dangling pins и неподключённые power pins.
10. Сделай backup mcp-test, затем откати последнее изменение.

Команды Windows:

```powershell
uv sync
uv run doctor
uv run start-mcp
uv run pytest tests/test_smoke.py -v
uv run kicad-ai example
uv run kicad-ai open projects\examples\mcp-test\mcp-test.kicad_pro
```
