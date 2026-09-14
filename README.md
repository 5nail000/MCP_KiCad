# KiCad AI — локальная среда Cursor → MCP → KiCad

## 1. What is this?

Рабочая среда для **AI-assisted engineering** в KiCad: LLM через MCP создаёт и правит **настоящие** `.kicad_sch` / `.kicad_pro`, проверяет связность, гоняет ERC/DRC и BOM через официальный `kicad-cli`. SKiDL — опциональный Python-слой; KiCad остаётся источником истины.

Это не генератор картинок и не mock. Схему можно открыть в KiCad 10.

## 2. Architecture

```
Cursor Agent  --stdio MCP-->  kicad-ai (whitelist + backup + logs)
                                |                         |
                                v                         v
                         kicad-sch-api 0.5.6          kicad-cli 10.0.6
                                |                     ERC / DRC / netlist
                                +-----> projects/**  (source of truth)

                         SKiDL 2.3.0  --> skidl_lab/  (blocks, tests, generated netlists)
                                          never overwrites projects/*.kicad_sch
```

- Schematic engine: пакет [`kicad-sch-api`](https://pypi.org/project/kicad-sch-api/) (реальный S-expression parser/writer).
- ERC / DRC / BOM / netlist / `sch upgrade`: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`.
- SKiDL 2.3.0 (`KICAD10`): блоки и Python ERC в `skidl_lab/` (не пакетный каталог `skidl/`, чтобы не перекрыть PyPI).
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

создаёт `projects/examples/mcp-test/` (12V → предохранитель → R-78E5.0-0.5 → 5V + LED). Рядом лежит тестовая плата `mcp-test.kicad_pcb` (не для производства). `kicad-ai example` с overwrite перезапишет каталог, после этого плату нужно собрать снова скриптом из §11.

## 8. Working with existing projects

1. `list_projects` / `load_schematic`
2. `get_schematic_info` + `inspect_connectivity`
3. Предложить изменение
4. `save_schematic` (backup создаётся автоматически)
5. `validate_project` (ERC + DRC; нет PCB → DRC SKIPPED)
6. Показать summary

Проекты пользователя кладите в `projects/user/`. Каталог `projects/` в `.gitignore` — схемы и платы не попадают в git, только локально. Не пишите вне workspace: MCP это запретит.

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
uv run kicad-ai validate projects\examples\mcp-test
uv run pytest -v
.\scripts\open-kicad.ps1
```

Doctor проверяет KiCad, Python 3.12, uv, Git, kicad-sch-api, SKiDL, `.cursor/mcp.json`, workspace.

`validate` гоняет настоящий `kicad-cli sch erc` и `kicad-cli pcb drc`. Если `.kicad_pcb` нет, DRC = SKIPPED (не PASS).

Python-тесты: `tests/test_electrical.py` (KiCad ERC/DRC/netlist) и `skidl_lab/tests/` (SKiDL ERC). SKiDL не пишет схему проекта.

## 11. PCB

MCP **не создаёт** `.kicad_pcb`: ни автоматически после схемы, ни по запросу из Cursor. `create_project` пишет только `.kicad_pro` + `.kicad_sch`. Tool `run_drc` / `validate_project` при отсутствии платы возвращают **SKIPPED** (это не PASS и не проверка разводки).

У примеров уже есть **тестовые** платы (smoke для DRC и 2D/3D render, не Gerber). Пересборка только через pcbnew KiCad 10:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" scripts\build_mcp_test_pcb.py
uv run kicad-ai validate projects\examples\mcp-test

& "C:\Program Files\KiCad\10.0\bin\python.exe" scripts\build_oxy_pcb.py
uv run kicad-ai validate projects\oxy\oxy
uv run kicad-ai render-pcb projects\oxy\oxy
uv run kicad-ai render-3d projects\oxy\oxy
```

`mcp-test`: F1, U1, R1, D1, 40×26 мм. `oxy`: F1, J1/J2 (XH2.54), R1, D1, 55×30 мм, GND/GNDA разведены.

Готовую к производству плату MCP не соберёт. Нормальный путь для своих проектов — KiCad GUI:

```powershell
uv run kicad-ai open projects\examples\mcp-test\mcp-test.kicad_pro
```

1. PCB Editor (если файла платы нет, KiCad создаст пустой `*.kicad_pcb`).
2. **Update PCB from Schematic** (`F8`) — футпринты и нетлист со схемы, не разводка.
3. Контур, расстановка, дорожки, полигоны, крепёж — руками в pcbnew.
4. DRC в PCB Editor, затем снова `uv run kicad-ai validate …` (DRC уже не SKIPPED).

`Update PCB from Schematic` — не «плата на печать». Gerber / drill / Pick & Place в этой среде **не реализованы**. Не просите агента имитировать их.

## 12. skidl_lab

[`skidl_lab/`](skidl_lab/README.md) — опциональный Python-слой на SKiDL 2.3.0 (`KICAD10`). Каталог назван `skidl_lab`, а не `skidl`: имя `skidl` занято пакетом PyPI (`import skidl` vs `import skidl_lab`).

KiCad-файлы в `projects/` остаются источником истины. SKiDL **не** перезаписывает `.kicad_sch` / `.kicad_pcb` / `.kicad_pro`. Нетлисты только в `skidl_lab/generated/`.

| Путь | Назначение |
|---|---|
| `skidl_lab/blocks/` | Переиспользуемые блоки (`led_indicator`, `rail_12v_5v`) |
| `skidl_lab/circuits/` | Сборки из блоков; `mcp_test_equivalent` повторяет *архитектуру* примера, но не заменяет `projects/examples/mcp-test` |
| `skidl_lab/tests/` | SKiDL ERC в pytest |
| `skidl_lab/generated/` | Артефакты (gitignore), не схема проекта |

MCP: `list_skidl_blocks`, `run_skidl_erc`, `export_skidl_netlist` (отказ, если путь в `projects/` или расширение `.kicad_sch`).

```powershell
uv run kicad-ai skidl-erc led_indicator
uv run kicad-ai skidl-erc rail_12v_5v
```

## 13. Visualization

Картинки строятся из `.kicad_sch` / `.kicad_pcb` через **kicad-cli**, не через AI/Blender/скриншот.

```powershell
uv run python scripts/render_project.py projects\examples\mcp-test
uv run kicad-ai render-schematic projects\examples\mcp-test
uv run kicad-ai render-pcb projects\examples\mcp-test
uv run kicad-ai render-3d projects\examples\mcp-test
```

Выход (gitignore): `renders/<project>/schematic|pcb|3d/` и `renders/render_report.json`.

| Запрос | Tool | Движок |
|---|---|---|
| Покажи схему | `render_schematic` | `kicad-cli sch export svg/pdf` → PNG |
| Покажи плату | `render_pcb` | `kicad-cli pcb export svg` |
| Плата в 3D | `render_pcb_3d` | `kicad-cli pcb render` |
| Весь проект | `render_project` | всё доступное; нет PCB → SKIPPED |

Темы `light` / `dark` (dark — presentation invert чёрной туши, геометрия та же). Виды схемы: `full` и имена из [`render.yaml`](render.yaml) (`power`, `indicator`, …) — SKIPPED, если на листе нет указанных reference. DPI: preview 150 / docs 300 / large 600. Кадрирование SVG по bounding box + `render.margin` в миллиметрах (по умолчанию 15, чтобы не резать labels и не оставлять пустой лист).

Авторендер после validation выключен (`automation.render_after_validation: false`). Устаревший PNG не показывается: `*.meta.json` хранит `source_hash`, при изменении схемы рендер пересобирается.

Нет `.kicad_pcb` — PCB/3D не симулируются. 3D-модели отсутствуют → WARNING, пайплайн продолжается.

## 14. Troubleshooting

См. [docs/troubleshooting.md](docs/troubleshooting.md). Логи: `logs/kicad-ai-YYYYMMDD.log` (каждая строка начинается с времени). Traceback не скрывается.

## 15. Example prompts for LLM

1. Создай проект `projects/user/pump-controller` с входом 12V, предохранителем и DC-DC 5V.
2. Прочитай `projects/examples/mcp-test` и перечисли компоненты и цепи.
3. Добавь в mcp-test конденсатор 100nF на выход 5V, сохрани backup и покажи connectivity.
4. Найди в библиотеках KiCad символ предохранителя, не создавай новый.
5. Соедини выход U1 с net `VOUT_5V` через label, не считая пересечение проводов соединением.
6. Прогони `validate_project` по текущей схеме, объясни ERC и статус DRC (PASS/FAIL/SKIPPED).
7. Сгенерируй BOM CSV для mcp-test.
8. Добавь защиту от обратной полярности (диод) на вход 12V, не меняя существующие reference.
9. Покажи dangling pins и неподключённые power pins.
10. Сделай backup mcp-test, затем откати последнее изменение.
11. Прогони SKiDL ERC для блока `led_indicator`; не пиши из SKiDL в `projects/`.
12. Плату проекта не генерируй через MCP. Для mcp-test тестовый `.kicad_pcb` уже есть; для своих плат — KiCad GUI и Update PCB from Schematic.
13. Покажи схему mcp-test (`render_schematic`), не генерируй картинку нейросетью.
14. Покажи плату mcp-test в 2D и 3D (`render_pcb`, `render_pcb_3d`). Если у проекта нет `.kicad_pcb` — SKIPPED, без фейковой картинки.

Команды Windows:

```powershell
uv sync
uv run doctor
uv run start-mcp
uv run pytest -v
uv run kicad-ai example
uv run kicad-ai validate projects\examples\mcp-test
uv run kicad-ai skidl-erc led_indicator
uv run python scripts/render_project.py projects\examples\mcp-test
uv run kicad-ai open projects\examples\mcp-test\mcp-test.kicad_pro
```
