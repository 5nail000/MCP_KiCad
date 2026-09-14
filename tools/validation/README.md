# tools/validation

Настоящие проверки (не mock):

- ERC: `kicad_ai.kicad_cli.run_erc` → `kicad-cli sch erc`
- DRC: `kicad_ai.kicad_cli.run_drc` → `kicad-cli pcb drc`
- Сводка: `kicad_ai.validate.validate_project`
- SKiDL ERC: `kicad_ai.skidl_runtime.run_block_erc` (не пишет `.kicad_sch` проекта)
- Pytest: `tests/test_electrical.py`, `skidl_lab/tests/`, `tests/test_render.py`
- Рендер: `kicad_ai.render` → `kicad-cli` SVG/PDF/3D PNG (не AI)

Нет платы → DRC SKIPPED с причиной. Не подменять это PASS. Пример mcp-test содержит тестовый `.kicad_pcb`, поэтому DRC там должен реально выполниться.
