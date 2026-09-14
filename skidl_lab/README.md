# SKiDL lab

Опциональный Python-слой для блоков, экспериментов и ERC в SKiDL.

Каталог назван `skidl_lab`, а не `skidl`: имя `skidl` занято пакетом PyPI. Импорт библиотеки — `import skidl`, импорт наших блоков — `import skidl_lab`.

## Правила

- Источник истины для реальных плат — KiCad-файлы в `projects/`.
- Этот слой **не** перезаписывает `.kicad_sch` / `.kicad_pcb` / `.kicad_pro`.
- Артефакты только в `generated/` (netlist). Это не вторая копия схемы проекта.
- Блок `rail_12v_5v` — инженерный эксперимент с той же *архитектурой*, что `projects/examples/mcp-test`. Он не заменяет и не синхронизирует mcp-test.

```text
KiCad projects/  ──validation──►  ERC / DRC / pytest  ──► PASS/FAIL

skidl_lab/       ──► blocks, test circuits, SKiDL ERC, generated netlists
```
