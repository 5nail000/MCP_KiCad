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
8. После правки: backup (делается при save), reload, `inspect_connectivity`, `run_erc`.
9. Проверяй dangling pins, незадействованные power pins, короткие замыкания, конфликтующие net names, питание.
10. Изменение схемы — инженерный артефакт. Его место в Git history.

## MCP tools

Проект: `list_projects`, `create_project`, `backup_project`, `restore_backup`, `list_project_backups`.

Схема: `load_schematic`, `save_schematic`, `get_schematic_info`.

Компоненты: `search_symbols`, `get_symbol_info`, `add_component`, `list_components`, `update_component`, `remove_component`.

Связность: `get_component_pins`, `connect_pins`, `add_wire`, `add_label`, `add_power_symbol`, `add_junction`, `inspect_connectivity`, `are_pins_connected`.

Проверки: `run_erc`, `export_netlist`, `export_bom`.

PCB, DRC, Gerber, SPICE, LCSC в этой версии **не реализованы**. Не имитируй их.

## Datasheets

Для нетривиальных частей смотри `components/<part>/notes.md` и `docs/datasheets/`. Не доверяй одному только имени компонента: проверь Vin, ток, pinout, AMR.
