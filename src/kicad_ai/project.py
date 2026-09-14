"""Create KiCad 10 project files (.kicad_pro + .kicad_sch) inside the workspace."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
import kicad_sch_api as ksa

from kicad_ai.backup import backup_project
from kicad_ai.config import get_workspace
from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import PathDenied, assert_allowed, find_lock_files

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def list_projects() -> list[dict[str, Any]]:
    workspace = get_workspace()
    projects_root = workspace / "projects"
    results: list[dict[str, Any]] = []
    if not projects_root.is_dir():
        return results
    for pro in sorted(projects_root.rglob("*.kicad_pro")):
        sch = pro.with_suffix(".kicad_sch")
        pcb = pro.with_suffix(".kicad_pcb")
        results.append(
            {
                "name": pro.stem,
                "project": str(pro),
                "schematic": str(sch) if sch.is_file() else None,
                "pcb": str(pcb) if pcb.is_file() else None,
                "relative": str(pro.parent.relative_to(workspace)).replace("\\", "/"),
            }
        )
    return results


def create_project(
    name: str,
    *,
    location: str = "user",
    title: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    if not _NAME_RE.match(name):
        raise ValueError("Project name must start with a letter and contain only A-Z, a-z, 0-9, . _ -")
    workspace = get_workspace()
    loc = location.strip().replace("\\", "/").strip("/") or "user"
    if loc in {"user", "examples"}:
        project_dir = workspace / "projects" / loc / name
    else:
        project_dir = assert_allowed(workspace / "projects" / loc / name, write=True)
        if not str(project_dir).lower().startswith(str((workspace / "projects").resolve()).lower()):
            raise PathDenied("Projects must be created under projects/")

    project_dir = assert_allowed(project_dir, write=True)
    if project_dir.exists() and any(project_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Project already exists: {project_dir}. Pass overwrite=true to replace it.")
    if overwrite and project_dir.exists():
        backup_project(project_dir)
        shutil.rmtree(project_dir)

    project_dir.mkdir(parents=True, exist_ok=True)
    install = require_kicad()
    logger = get_logger()

    schematic_path = project_dir / f"{name}.kicad_sch"
    project_path = project_dir / f"{name}.kicad_pro"

    sch = ksa.create_schematic(title or name)
    sch.set_title_block(title=title or name)
    sch.save(schematic_path)
    sheet_uuid = str(sch.uuid)

    _write_project_file(project_path, name=name, sheet_uuid=sheet_uuid, template_dir=install.template_dir)
    _copy_lib_tables(project_dir, install.template_dir)

    locks = find_lock_files(project_dir)
    logger.info("Created KiCad project %s", project_path)
    return {
        "success": True,
        "name": name,
        "project_dir": str(project_dir),
        "project": str(project_path),
        "schematic": str(schematic_path),
        "uuid": sheet_uuid,
        "locks": [str(p) for p in locks],
    }


def _write_project_file(path: Path, *, name: str, sheet_uuid: str, template_dir: Path) -> None:
    template = template_dir / "EuroCard160mmX100mm" / "EuroCard160mmX100mm.kicad_pro"
    if template.is_file():
        data = json.loads(template.read_text(encoding="utf-8"))
    else:
        data = {"meta": {"version": 3}, "sheets": []}
    data.setdefault("meta", {})
    data["meta"]["filename"] = f"{name}.kicad_pro"
    data["meta"]["version"] = data["meta"].get("version", 3)
    data["sheets"] = [[sheet_uuid, "Root"]]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _copy_lib_tables(project_dir: Path, template_dir: Path) -> None:
    for filename in ("sym-lib-table", "fp-lib-table"):
        source = template_dir / filename
        if source.is_file():
            shutil.copy2(source, project_dir / filename)
