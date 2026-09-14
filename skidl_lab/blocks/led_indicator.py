"""+5V → resistor → LED → GND. SKiDL experiment block, not a KiCad project file."""

from __future__ import annotations

from skidl import Circuit, Net, Part, POWER


def build(circuit: Circuit | None = None) -> Circuit:
    circ = circuit or Circuit()
    circ.no_files = True
    vcc = Net("+5V", circuit=circ)
    gnd = Net("GND", circuit=circ)
    vcc.drive = POWER
    gnd.drive = POWER
    pwr = Part("power", "+5V", circuit=circ)
    pgnd = Part("power", "GND", circuit=circ)
    resistor = Part("Device", "R", value="1k", circuit=circ)
    led = Part("Device", "LED", circuit=circ)
    vcc += pwr[1]
    vcc += resistor[1]
    resistor[2] += led["A"]
    gnd += led["K"]
    gnd += pgnd[1]
    return circ
