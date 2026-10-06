# Hardware notes — Rev B

The [schematic PDF](schematic-rev-b.pdf) contains three sheets:

1. Controller, DAC, and power connections.
2. Switched cell array and current-summing amplifiers.
3. Programming driver, reference buffer, and ADC interface.

## Signal path

| Block | Implementation |
| --- | --- |
| Controller | Raspberry Pi Pico; USB link to the future Python host |
| Input voltages | DAC80508ZRTET OUT0–3; 0–0.2 V proposed read range |
| Cell selection | Two MAX333ACPP+ chips, eight independent SPDT switches |
| Cells | MR1–MR8, external two-terminal sockets; physical device still to be selected |
| Column readout | U1/U2 TLV172; 10 kΩ feedback, 100 pF parallel compensation |
| Reference buffer | U8 TLV172; nominal 2.5 V |
| Programming driver | U9 TLV172; equal 10 kΩ resistors, 1 kΩ series output resistor |
| ADC interface | 30 kΩ/10 kΩ dividers, TLV9004 buffers, BAT54S clamps, 1 kΩ/10 nF filters |
| Measurement | ADS1115 at I2C address 0x48; AIN0−AIN3 and AIN1−AIN3 |

The schematic is a prototype design, not a fabrication-ready PCB. Compensation, protection, device compliance, and layout still need physical validation.

## Cell mapping

| Input | DAC channel | Column A | Column B |
| --- | --- | --- | --- |
| PIXEL_1 | OUT0 | MR1 | MR5 |
| PIXEL_2 | OUT1 | MR2 | MR8 |
| PIXEL_3 | OUT2 | MR3 | MR7 |
| PIXEL_4 | OUT3 | MR4 | MR6 |

The example resistances are A = [60, 60, 120, 120] kΩ and B = [120, 120, 60, 60] kΩ. These are simulation assignments, not measured or permanently programmed device values.

## Pico signals

| Function | GPIO |
| --- | --- |
| ADC SDA / SCL | GP4 / GP5 |
| Select MR1 / MR2 / MR3 / MR4 | GP6 / GP7 / GP8 / GP9 |
| Select MR5 / MR8 / MR7 / MR6 | GP10 / GP11 / GP12 / GP13 |
| DAC MISO / CS / SCLK / MOSI | GP16 / GP17 / GP18 / GP19 |

These are GPIO numbers, not physical header-pin numbers. LOW selects the pixel/read path; HIGH selects the program path. The selection pins have 100 kΩ pulldowns. Future firmware must allow only one selected cell during a write.

## Readout configuration

Enable the DAC's internal reference, set REF-DIV = 0, and use output-buffer gain 1 for the nominal 2.5 V range. The Z variant has SDO/ALARM; it is not the ZC variant with CLR.

The ADC baseline is 1.875 V. Differential readings remove that offset; multiply by four to reconstruct the raw amplifier output. The proposed initial ADC setting is ±0.256 V, single-shot, 128 SPS. Two sequential conversions take about 15.6 ms before communication overhead. Larger differential signals can clip, and 16-bit conversion does not imply 16-bit system accuracy.

## Programming and power

- Pico is powered by USB; its 3.3 V rail powers digital logic, the ADC, and U10. The analog section uses an external ±5 V supply with common ground. Analog +5 V is not connected to Pico VBUS or VSYS.
- JP1 pins 1–2 disarm programming by grounding the bus. Pins 2–3 connect the driver through the 1 kΩ resistor. Use one shunt.
- Set PROG_CMD to 1.25 V before arming: this produces a nominal zero driver output. Commands 0.25 V and 2.25 V produce nominal −2 V and +2 V.
- The 1 kΩ resistor limits current passively; it is not regulated device compliance. The actual cell voltage is approximately `Vdriver × Rcell / (Rcell + 1000 + Rswitch)`.
- Proposed write sequence: pixel inputs zero → driver zero → select one cell → timed pulse → driver zero → deselect → low-voltage read and verify.

Start bring-up with fixed resistors and JP1 disarmed. Keep USB/3.3 V on before applying the analog rails; remove analog power before USB. Read voltage, write voltage, polarity, and pulse duration must be chosen from real-device characterization. The earlier educational model's ±2 V pulses are not a device specification.
