# KiCad AI workspace

Этот репозиторий — среда, в которой LLM работает с **настоящими** проектами KiCad через MCP.

## Обязательные правила

1. Сначала читай существующий проект. Не пересоздавай его без необходимости.
2. Не удаляй компоненты молча. `remove_component` только с явным подтверждением.
3. Не меняй reference designators без причины.
4. Сохраняй существующие net names.
5. Не придумывай part number. Ищи символ в официальных библиотеках KiCad.
6. Не считай два провода соединёнными только потому, что они пересекаются на схеме.
7. Различай: провод, графическое пересечение, junction, net label, power symbol.
8. После правки: backup (делается при save), reload, `inspect_connectivity`, `validate_project` (ERC + DRC).
9. Проверяй dangling pins, незадействованные power pins, короткие замыкания, конфликтующие net names, питание.
10. Изменение схемы — инженерный артефакт. Его место в Git history.
11. **KiCad — источник истины.** SKiDL не перезаписывает `.kicad_sch` / `.kicad_pcb` / `.kicad_pro` в `projects/`.
12. Нет `.kicad_pcb` → DRC и PCB/3D render = **SKIPPED**, это не PASS и не имитация платы. У `projects/examples/mcp-test` тестовая плата уже есть (не для производства).
13. Картинки схемы/платы — только `kicad-cli` (SVG/PDF/3D PNG). Не генерируй изображения нейросетью.

## MCP tools

Проект: `list_projects`, `create_project`, `backup_project`, `restore_backup`, `list_project_backups`.

Схема: `load_schematic`, `save_schematic`, `get_schematic_info`.

Компоненты: `search_symbols`, `get_symbol_info`, `add_component`, `list_components`, `update_component`, `remove_component`.

Связность: `get_component_pins`, `connect_pins`, `add_wire`, `add_label`, `add_power_symbol`, `add_junction`, `inspect_connectivity`, `are_pins_connected`.

Проверки: `run_erc`, `run_drc`, `validate_project`, `export_netlist`, `export_bom`.

Рендер (kicad-cli, не AI): `render_schematic`, `render_pcb`, `render_pcb_3d`, `render_project`, `get_render_report`. Нет `.kicad_pcb` → PCB/3D = SKIPPED.

SKiDL (опционально, не source of truth): `list_skidl_blocks`, `run_skidl_erc`, `export_skidl_netlist`.

Gerber, SPICE, LCSC в этой версии **не реализованы**. Не имитируй их.

## Datasheets

Для нетривиальных частей смотри `components/<part>/notes.md` и `docs/datasheets/`. Не доверяй одному только имени компонента: проверь Vin, ток, pinout, AMR.
