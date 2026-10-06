"""Check Rev B connectivity and 17 idealized DC operating points.

Adapted from the project's original validation script for portable paths and
pin-based lookup. ngspice models the exported resistor connections, fixed cell
resistances, 50-ohm closed switches, and voltage-controlled ideal op amps.
It does NOT model programming dynamics, converter protocols, or firmware.
"""

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from netlist import Netlist

HERE = Path(__file__).resolve().parent
CELLS = {1: 60_000, 2: 60_000, 3: 120_000, 4: 120_000,
         5: 120_000, 8: 120_000, 7: 60_000, 6: 60_000}
SWITCHES = (("U6", (1, 2, 3, 4)), ("U7", (5, 8, 7, 6)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_connectivity(net):
    count = 0

    def connected(anchor, expected, exact=False):
        nonlocal count
        got = net.connections(*anchor)
        wanted = set(expected.split())
        require(got == wanted if exact else wanted <= got,
                f"Connectivity mismatch at {anchor}: missing {wanted - got}, "
                f"extra {got - wanted}")
        count += 1

    for row, pin in enumerate((4, 7, 14, 17), 1):
        connected(("U4", row + 1),
                  f"U4.{row + 1} U6.{pin} U7.{pin}", True)
    connected(("U1", 3), "MR1.2 MR2.2 MR3.2 MR4.2 U1.3 R5.1 C8.1", True)
    connected(("U2", 3), "MR5.2 MR8.2 MR7.2 MR6.2 U2.3 R6.1 C9.1", True)
    for column, (chip, cells) in enumerate(SWITCHES):
        pico_pins = (9, 10, 11, 12) if column == 0 else (14, 15, 16, 17)
        for row, (cell, com, sel, pico) in enumerate(zip(
                cells, (3, 8, 13, 18), (1, 10, 11, 20), pico_pins)):
            connected((f"MR{cell}", 1), f"MR{cell}.1 {chip}.{com}", True)
            connected((chip, sel),
                      f"{chip}.{sel} A1.{pico} R{19 + 4 * column + row}.1",
                      True)
    connected(("JP1", 2),
              "JP1.2 TP8.1 U6.2 U6.9 U6.12 U6.19 "
              "U7.2 U7.9 U7.12 U7.19", True)
    for anchor, expected in (
        (("U4", 12), "A1.22 U4.12 R1.2"),
        (("U4", 13), "A1.24 U4.13"),
        (("U4", 14), "A1.25 U4.14"),
        (("U4", 15), "A1.21 U4.15"),
        (("U5", 9), "A1.6 U5.9 R2.2"),
        (("U5", 10), "A1.7 U5.10 R3.2"),
    ):
        connected(anchor, expected, True)
    for anchor, expected in (
        (("U5", 4), "U5.4 R12.2 C18.1"),
        (("U5", 5), "U5.5 R15.2 C19.1"),
        (("U5", 7), "U5.7 R18.2 C20.1"),
        (("U5", 3), "U4.6 U4.17 U5.1 U5.3 U6.6 U7.6 U10.11 A1.3"),
        (("U4", 7), "U4.7 U1.5 U2.5 U6.16 U7.16 U8.5 U9.5"),
        (("U1", 2), "U1.2 U2.2 U6.5 U7.5 U8.2 U9.2"),
        (("U5", 8), "A1.36 U4.16 U5.8 U10.4"),
    ):
        connected(anchor, expected)
    unexpected = [name for name, pins in net.members.items()
                  if len(pins) < 2 and not name.startswith("unconnected-")]
    require(not unexpected, f"Unexpected singleton nets: {unexpected}")
    unconnected = set().union(*(pins for name, pins in net.members.items()
                                if name.startswith("unconnected-")))
    expected = {f"A1.{pin}" for pin in (
        1, 2, 4, 5, 19, 20, 26, 27, 29, 30, 31, 32, 34, 35, 37, 39, 40)}
    expected |= {"U4.9", "U4.10", "U4.11", "U5.2", "U6.15", "U7.15"}
    require(unconnected == expected, "Intentional no-connect list differs")
    return count


def base_deck(net):
    node = net.node
    lines = ["Rev B simplified analog DC check"]
    for ref, value in net.values.items():
        if re.fullmatch(r"R\d+", ref):
            lines.append(f"{ref} {node(ref, 1)} {node(ref, 2)} {value.split()[0]}")
    # VCVS op amps: Aol = 1e7; no bandwidth, rail limiting, or offset model.
    for ref in ("U1", "U2", "U8", "U9"):
        lines.append(f"E{ref} {node(ref, 4)} 0 {node(ref, 1)} {node(ref, 3)} 1e7")
    for positive, negative, output in ((3, 2, 1), (5, 6, 7),
                                       (10, 9, 8), (12, 13, 14)):
        lines.append(f"Ebuf{output} {node('U10', output)} 0 "
                     f"{node('U10', positive)} {node('U10', negative)} 1e7")
    for name, pin, volts in (("v3", ("U5", 8), 3.3),
                             ("vp", ("U4", 7), 5),
                             ("vn", ("U1", 2), -5),
                             ("ref", ("U4", 1), 2.5)):
        lines.append(f"V{name} {node(*pin)} 0 {volts}")
    for cell, ohms in CELLS.items():
        lines.append(f"Rcell{cell} {node(f'MR{cell}', 1)} "
                     f"{node(f'MR{cell}', 2)} {ohms}")
    return lines


def simulate(net, executable):
    node = net.node
    base = base_deck(net)
    observed = [node(*pin) for pin in (
        ("U1", 4), ("U2", 4), ("U5", 4), ("U5", 5), ("U5", 7), ("R9", 2))]
    cases = [(None, 1.25)] + [(cell, command)
                              for cell in CELLS for command in (0.25, 2.25)]
    report = []
    with tempfile.TemporaryDirectory(prefix="memristor-dc-") as temp:
        for selected, command in cases:
            lines = base.copy()
            pixels = (0.2, 0.1, 0.1, 0.1) if selected is None else (0, 0, 0, 0)
            for row, voltage in enumerate(pixels, 1):
                lines.append(f"Vpixel{row} {node('U4', row + 1)} 0 {voltage}")
            lines.append(f"Vcmd {node('U4', 8)} 0 {command}")
            lines.append(f"Rarm {node('JP1', 2)} {node('JP1', 3)} 1u")
            for chip, cells in SWITCHES:
                for cell, nc, no, com, sel in zip(
                        cells, (4, 7, 14, 17), (2, 9, 12, 19),
                        (3, 8, 13, 18), (1, 10, 11, 20)):
                    writing = cell == selected
                    lines.append(f"Rsw{cell} {node(chip, com)} "
                                 f"{node(chip, no if writing else nc)} 50")
                    lines.append(f"Vsel{cell} {node(chip, sel)} 0 "
                                 f"{3.3 if writing else 0}")
            lines += [".control", "set numdgt=12", "op",
                      "print " + " ".join(f"v({n})" for n in observed),
                      "quit", ".endc", ".end"]
            deck = Path(temp) / "case.cir"
            deck.write_text("\n".join(lines) + "\n")
            run = subprocess.run([executable, "-b", str(deck)],
                                 capture_output=True, text=True, timeout=30)
            require(run.returncode == 0, run.stdout + run.stderr)
            values = {key: float(value) for key, value in re.findall(
                r"v\((n\d+)\)\s*=\s*([-+\deE.]+)", run.stdout)}
            require(all(n in values for n in observed), run.stdout + run.stderr)
            va, vb, aa, ab, baseline, prog = [values[n] for n in observed]
            require(all(math.isfinite(v) for v in values.values()),
                    "Non-finite simulation result")
            for raw, conditioned in ((va, aa), (vb, ab)):
                require(abs(4 * (conditioned - baseline) - raw) < 8e-6,
                        "ADC reconstruction mismatch")
            if selected is None:
                expected_a = -10_000 * (0.2 / 60_050 + 0.1 / 60_050
                                        + 0.1 / 120_050 + 0.1 / 120_050)
                expected_b = -10_000 * (0.2 / 120_050 + 0.1 / 120_050
                                        + 0.1 / 60_050 + 0.1 / 60_050)
                require(abs(va - expected_a) < 1e-6
                        and abs(vb - expected_b) < 1e-6, "Read output mismatch")
            else:
                expected = -10_000 * (2 * command - 2.5) / (CELLS[selected] + 1050)
                active, other = (va, vb) if selected <= 4 else (vb, va)
                require(abs(active - expected) < 2e-6, "Write-path mismatch")
                require(abs(other) < 1e-7, "Inactive column is not isolated")
            report.append(dict(selected_cell=selected, command_V=command,
                               OUT_A_V=va, OUT_B_V=vb, ADC_A_V=aa, ADC_B_V=ab,
                               ADC_BASE_V=baseline, PROG_LIMITED_V=prog))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", type=Path, default=HERE / "connectivity.net")
    parser.add_argument("--connectivity-only", action="store_true")
    parser.add_argument("--ngspice", default="ngspice", help="Executable name or path")
    parser.add_argument("--output", type=Path, default=HERE / "results" / "dc-results.json")
    args = parser.parse_args()
    net = Netlist(args.netlist)
    count = check_connectivity(net)
    print(f"PASS: {count} explicit connectivity checks; no unexpected singleton nets.")
    if args.connectivity_only:
        return
    executable = shutil.which(args.ngspice)
    if executable is None:
        parser.error("ngspice not found; install it or use --ngspice /path/to/ngspice")
    report = simulate(net, executable)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {len(report)} DC cases; read outputs, write paths, and ADC scaling.")
    print(f"Read: A={report[0]['OUT_A_V']:.8f} V, B={report[0]['OUT_B_V']:.8f} V")
    print(f"Results: {args.output}")
    print("Idealized DC checks only; no physical switching or firmware validation.")


if __name__ == "__main__":
    main()
