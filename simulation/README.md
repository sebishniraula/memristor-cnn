# Circuit calculations and checks

These scripts reproduce the prototype's math and validate its exported wiring.
They do not operate hardware or implement CNN training.

## Run

Use Python 3.10+ from the repository root. No pip dependencies are needed.

```bash
python3 simulation/read_example.py
python3 simulation/check_circuit.py --connectivity-only
```

For the analog DC cases, install the ngspice command-line program and run:

```bash
python3 simulation/check_circuit.py
# If ngspice is not on PATH:
python3 simulation/check_circuit.py --ngspice /path/to/ngspice
```

The script writes `simulation/results/dc-results.json`; that generated directory
is ignored by Git. `--netlist` selects another KiCad S-expression netlist and
`--output` changes the JSON destination. The expected pins and component roles
are specific to this design.

## What the code does

| File | Responsibility |
| --- | --- |
| `read_example.py` | Computes `W x`, ideal read voltages, ADC conditioning, and the effect of an assumed 50 Ω switch resistance. Prints DAC codes but keeps requested voltages unquantized in the calculation. |
| `netlist.py` | Reads the KiCad S-expression export and maps physical `(reference, pin)` pairs to nets. |
| `check_circuit.py` | Checks 36 expected wiring relationships, the intentional no-connect list, and unexpected singleton nets. Generates one read case plus 16 selected-cell write-path cases for ngspice. |
| `connectivity.net` | Rev B connectivity export. The machine-specific source path was removed; pin memberships and component values were retained. |
| `reference-results.json` | Saved output from the documented ngspice run, for inspection without installing the simulator. |

The checker is a portable cleanup of the original project validation script.
The numerical read example was added when preparing this repository to make the
README calculations directly reproducible.

## Simulation assumptions

- Each memristor is represented by a **fixed 60 kΩ or 120 kΩ resistor**. The
  write cases verify applied voltage/current paths, not a changing stored weight.
- A closed switch is 50 Ω; an open switch is omitted. There is no leakage,
  capacitance, or switching-transient model.
- Op amps are voltage-controlled sources with open-loop gain `1e7`. They have no
  bandwidth, rail saturation, offset, noise, or output-current limit.
- DAC outputs, supplies, and reference are ideal voltage sources. The ADC is
  observed as a voltage node; its sampling, loading, conversion, and I2C behavior
  are not simulated. Clamp diodes are omitted; capacitors are open at DC.
- The programming jumper is modeled as armed with a near-zero resistance.

Expected read outputs with the 50 Ω switch assumption are approximately
`OUT_A = -0.0666181 V` and `OUT_B = -0.0582952 V`.

The included `reference-results.json` was regenerated on 2026-10-06 using
Python 3.12 and ngspice 42: all 36 connectivity checks and 17 DC cases passed.
The read case produced A = −0.06661808 V and B = −0.05829516 V. Tiny differences
from the ideal Ohm's-law values come from the finite open-loop gain in the
simplified op-amp model.

Checks accept 1 µV read-output error, 2 µV selected write-output error, 0.1 µV
inactive-column voltage, and 8 µV error when reconstructing a raw output from
the conditioned ADC nodes. These are numerical check tolerances, not promised
hardware accuracy.

No educational memristor `.lib` model is attached here: it was not fitted to a
physical device, and these particular checks only need fixed read resistances.
