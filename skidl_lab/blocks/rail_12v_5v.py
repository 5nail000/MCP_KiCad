"""12V → fuse → R-78E5.0-0.5 → 5V LED. Architecture experiment, not mcp-test itself."""

from __future__ import annotations

from skidl import Circuit, Net, Part, POWER


def build(circuit: Circuit | None = None) -> Circuit:
    """Same topology as projects/examples/mcp-test, stored only as SKiDL Python.

    Do not generate a .kicad_sch from this block into projects/.
    """
    circ = circuit or Circuit()
    circ.no_files = True
    vin = Net("+12V", circuit=circ)
    vin_fused = Net("VIN", circuit=circ)
    vout = Net("+5V", circuit=circ)
    gnd = Net("GND", circuit=circ)
    vin.drive = POWER
    vin_fused.drive = POWER
    vout.drive = POWER
    gnd.drive = POWER

    p12 = Part("power", "+12V", circuit=circ)
    p5 = Part("power", "+5V", circuit=circ)
    pgnd = Part("power", "GND", circuit=circ)
    pwr_flag = Part("power", "PWR_FLAG", circuit=circ)
    fuse = Part("Device", "Fuse", value="2A", circuit=circ)
    regulator = Part("Converter_DCDC", "R-78E5.0-0.5", circuit=circ)
    resistor = Part("Device", "R", value="1k", circuit=circ)
    led = Part("Device", "LED", circuit=circ)

    vin += p12[1]
    vin += fuse[1]
    vin_fused += fuse[2]
    vin_fused += regulator["IN"]
    vin_fused += pwr_flag[1]
    gnd += regulator["GND"]
    gnd += pgnd[1]
    vout += regulator["OUT"]
    vout += p5[1]
    vout += resistor[1]
    resistor[2] += led["A"]
    gnd += led["K"]
    return circ
