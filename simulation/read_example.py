"""Reproduce one four-input, two-output read; no hardware or packages needed.

The cells are fixed resistances during a read. This is a numerical explanation,
not a device-switching model, classifier, or Pico driver.
"""

INPUTS = (1.0, 0.5, 0.5, 0.5)
CELL_OHMS = ((60_000, 60_000, 120_000, 120_000),
             (120_000, 120_000, 60_000, 60_000))
INPUT_SCALE_V = 0.2
FEEDBACK_OHMS = 10_000
REFERENCE_V = 2.5
G0_SIEMENS = 1 / 60_000


def read_outputs(switch_ohms=0.0):
    """Return (raw output V, conditioned ADC input V) for each column."""
    voltages = [INPUT_SCALE_V * x for x in INPUTS]
    outputs = []
    for resistances in CELL_OHMS:
        current = sum(v / (r + switch_ohms)
                      for v, r in zip(voltages, resistances))
        raw = -FEEDBACK_OHMS * current
        outputs.append((raw, 0.25 * raw + 0.75 * REFERENCE_V))
    return outputs


def main():
    voltages = [INPUT_SCALE_V * x for x in INPUTS]
    codes = [round(v / REFERENCE_V * 65_536) for v in voltages]
    weights = [[(1 / r) / G0_SIEMENS for r in column]
               for column in CELL_OHMS]
    expected = [sum(w * x for w, x in zip(column, INPUTS))
                for column in weights]
    print(f"Patch: {list(INPUTS)}")
    print(f"Requested input voltages: {voltages} V")
    print(f"Nearest 16-bit DAC codes: {codes}")
    print(f"Dimensionless W x: {expected}")
    baseline = 0.75 * REFERENCE_V
    for switch in (0.0, 50.0):
        print(f"\nAssumed switch resistance: {switch:g} ohm")
        for name, (raw, adc) in zip("AB", read_outputs(switch)):
            differential = adc - baseline
            decoded = -4 * differential / (
                FEEDBACK_OHMS * INPUT_SCALE_V * G0_SIEMENS)
            print(f"  {name}: OUT={raw * 1000:.6f} mV, "
                  f"ADC={adc:.6f} V, decoded y={decoded:.6f}")
    print("\nCalculations use requested voltages, not quantized DAC outputs.")
    print("50 ohm is an illustrative switch assumption, not a measured value.")


if __name__ == "__main__":
    main()
