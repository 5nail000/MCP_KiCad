"""Build the oxy isolated DC-DC adapter PCB with KiCad pcbnew (smoke test, not production).

Run with KiCad's Python:

    & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" scripts\\build_oxy_pcb.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pcbnew is missing. Use KiCad's python.exe, not the project .venv:\n"
        '  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" scripts\\build_oxy_pcb.py'
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "oxy" / "oxy"
PCB_PATH = PROJECT / "oxy.kicad_pcb"
BOARD_W_MM = 55.0
BOARD_H_MM = 30.0
TRACK_MM = 0.35
EDGE_MM = 0.1


class TimestampFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} {record.levelname} {super().format(record)}"


def _logger() -> logging.Logger:
    logger = logging.getLogger("build_oxy_pcb")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(TimestampFormatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def _mm_point(x: float, y: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def _footprint_dir() -> Path:
    candidates = [
        Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints"),
        Path(r"C:\Program Files\KiCad\10.0\share\kicad\fp"),
    ]
    for path in candidates:
        if (path / "Connector_JST.pretty").is_dir():
            return path
    raise FileNotFoundError("KiCad 10 footprint libraries not found")


def _pad(footprint: "pcbnew.FOOTPRINT", number: str) -> "pcbnew.PAD":
    for pad in footprint.Pads():
        if pad.GetNumber() == str(number):
            return pad
    raise KeyError(f"{footprint.GetReference()} has no pad {number}")


def _net(board: "pcbnew.BOARD", name: str) -> "pcbnew.NETINFO_ITEM":
    found = board.FindNet(name)
    if found is not None and found.GetNetCode() > 0:
        return found
    item = pcbnew.NETINFO_ITEM(board, name)
    board.Add(item)
    return item


def _load_fp(fp_root: Path, lib: str, name: str) -> "pcbnew.FOOTPRINT":
    pretty = fp_root / f"{lib}.pretty"
    footprint = pcbnew.FootprintLoad(str(pretty), name)
    if footprint is None:
        raise FileNotFoundError(f"Cannot load {lib}:{name} from {pretty}")
    return footprint


def _edge_rect(board: "pcbnew.BOARD", width: float, height: float) -> None:
    corners = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height), (0.0, 0.0)]
    for (x1, y1), (x2, y2) in zip(corners, corners[1:]):
        segment = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        segment.SetLayer(pcbnew.Edge_Cuts)
        segment.SetStart(_mm_point(x1, y1))
        segment.SetEnd(_mm_point(x2, y2))
        segment.SetWidth(pcbnew.FromMM(EDGE_MM))
        board.Add(segment)


def _track(
    board: "pcbnew.BOARD",
    start: "pcbnew.VECTOR2I",
    end: "pcbnew.VECTOR2I",
    net: "pcbnew.NETINFO_ITEM",
    *,
    layer: int | None = None,
) -> None:
    item = pcbnew.PCB_TRACK(board)
    item.SetStart(start)
    item.SetEnd(end)
    item.SetWidth(pcbnew.FromMM(TRACK_MM))
    item.SetLayer(layer if layer is not None else pcbnew.F_Cu)
    item.SetNet(net)
    board.Add(item)


def _route(board: "pcbnew.BOARD", net: "pcbnew.NETINFO_ITEM", points: list["pcbnew.VECTOR2I"]) -> None:
    for start, end in zip(points, points[1:]):
        _track(board, start, end, net)


def _place(
    board: "pcbnew.BOARD",
    fp_root: Path,
    *,
    lib: str,
    name: str,
    ref: str,
    value: str,
    x: float,
    y: float,
    rotation: float = 0.0,
    nets: dict[str, "pcbnew.NETINFO_ITEM"],
) -> "pcbnew.FOOTPRINT":
    footprint = _load_fp(fp_root, lib, name)
    footprint.SetFPIDAsString(f"{lib}:{name}")
    footprint.SetReference(ref)
    footprint.SetValue(value)
    footprint.SetPosition(_mm_point(x, y))
    if rotation:
        footprint.SetOrientationDegrees(rotation)
    board.Add(footprint)
    for pad_number, net in nets.items():
        _pad(footprint, pad_number).SetNet(net)
    return footprint


def build() -> Path:
    logger = _logger()
    if not PROJECT.is_dir():
        raise FileNotFoundError(f"Project missing: {PROJECT}")
    fp_root = _footprint_dir()
    logger.info("footprints=%s", fp_root)

    board = pcbnew.CreateEmptyBoard()
    board.SetFileName(str(PCB_PATH))
    settings = board.GetDesignSettings()
    settings.SetCopperLayerCount(2)
    settings.m_TrackMinWidth = pcbnew.FromMM(0.2)
    settings.m_MinClearance = pcbnew.FromMM(0.2)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(0.5)
    settings.m_HoleToHoleMin = pcbnew.FromMM(0.25)

    nets = {
        "+12V": _net(board, "+12V"),
        "+5V": _net(board, "+5V"),
        "GND": _net(board, "GND"),
        "GNDA": _net(board, "GNDA"),
        "Net-(D1-A)": _net(board, "Net-(D1-A)"),
        "Net-(J1-Pin_1)": _net(board, "Net-(J1-Pin_1)"),
    }

    _edge_rect(board, BOARD_W_MM, BOARD_H_MM)

    # Primary (left): +12V on F1.1 (wire-in pad) -> J1 Vin+ ; J1 Gin- -> GND
    f1 = _place(
        board,
        fp_root,
        lib="Fuse",
        name="Fuse_0603_1608Metric",
        ref="F1",
        value="2A",
        x=9.0,
        y=13.0,
        rotation=0.0,
        nets={"1": nets["+12V"], "2": nets["Net-(J1-Pin_1)"]},
    )
    j1 = _place(
        board,
        fp_root,
        lib="Connector_JST",
        name="JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
        ref="J1",
        value="XH2.54 Vin",
        x=16.0,
        y=13.0,
        rotation=90.0,
        nets={"1": nets["Net-(J1-Pin_1)"], "2": nets["GND"]},
    )

    # Secondary (right): J2 Vout+ -> R1 -> D1 ; J2 Gout- + D1 K -> GNDA
    j2 = _place(
        board,
        fp_root,
        lib="Connector_JST",
        name="JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
        ref="J2",
        value="XH2.54 Vout 5V",
        x=39.0,
        y=13.0,
        rotation=90.0,
        nets={"1": nets["+5V"], "2": nets["GNDA"]},
    )
    r1 = _place(
        board,
        fp_root,
        lib="Resistor_SMD",
        name="R_0603_1608Metric",
        ref="R1",
        value="1k",
        x=47.0,
        y=9.0,
        rotation=0.0,
        nets={"1": nets["+5V"], "2": nets["Net-(D1-A)"]},
    )
    d1 = _place(
        board,
        fp_root,
        lib="LED_SMD",
        name="LED_0603_1608Metric",
        ref="D1",
        value="LED",
        x=47.0,
        y=18.0,
        rotation=90.0,
        nets={"1": nets["GNDA"], "2": nets["Net-(D1-A)"]},
    )

    for fp in (f1, j1, j2, r1, d1):
        fp.Value().SetVisible(False)
        fp.Reference().SetVisible(False)

    # J1/J2 rot90: pad1 at connector anchor, pad2 offset -2.5 mm in Y (avoid vertical bus at x=16/39)
    _route(
        board,
        nets["Net-(J1-Pin_1)"],
        [_pad(f1, "2").GetPosition(), _pad(j1, "1").GetPosition()],
    )
    _route(
        board,
        nets["+5V"],
        [
            _pad(j2, "1").GetPosition(),
            _mm_point(44.0, 13.0),
            _mm_point(44.0, 9.0),
            _pad(r1, "1").GetPosition(),
        ],
    )
    _route(
        board,
        nets["Net-(D1-A)"],
        [
            _pad(r1, "2").GetPosition(),
            _mm_point(49.0, 9.0),
            _mm_point(49.0, 17.2125),
            _pad(d1, "2").GetPosition(),
        ],
    )
    _route(
        board,
        nets["GNDA"],
        [
            _pad(j2, "2").GetPosition(),
            _mm_point(44.0, 10.5),
            _mm_point(44.0, 20.0),
            _mm_point(47.0, 20.0),
            _pad(d1, "1").GetPosition(),
        ],
    )

    comment = pcbnew.PCB_TEXT(board)
    comment.SetText("oxy adapter — isolated DC-DC module interface (not for production)")
    comment.SetLayer(pcbnew.Cmts_User if hasattr(pcbnew, "Cmts_User") else pcbnew.Dwgs_User)
    comment.SetPosition(_mm_point(27.5, 28.0))
    comment.SetTextSize(_mm_point(1.0, 1.0))
    comment.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(comment)

    if hasattr(board, "BuildConnectivity"):
        board.BuildConnectivity()
    pcbnew.SaveBoard(str(PCB_PATH), board)
    logger.info("wrote %s", PCB_PATH)
    return PCB_PATH


def main() -> int:
    logger = _logger()
    try:
        path = build()
    except Exception:
        logger.exception("failed to build oxy PCB")
        return 1
    logger.info("done pcb=%s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
