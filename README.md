# REW to AutoEQ

[繁體中文版](README.zh-TW.md)

Convert [REW](https://www.roomeqwizard.com/) (Room EQ Wizard) measurement exports into CSV files that [AutoEQ](https://autoeq.app) can read directly.

REW saves measurements as text files with comment headers (`* ...`) and columns such as `Freq(Hz), SPL(dB), Phase(degrees)`. AutoEQ expects a simple `frequency,raw` CSV with relative dB values. This tool bridges the two: it parses the REW export, filters and interpolates the response onto a log-spaced grid, optionally applies fractional-octave smoothing, normalizes to relative dB, and writes the AutoEQ-ready CSV.

## Features

- Parses REW text exports (comma or tab separated, with or without a header row)
- Handles common file encodings including UTF-8, Big5 and GB18030
- Filters the response to the requested frequency range (default 20 Hz - 20 kHz)
- Interpolates onto a 1/20 octave log grid, matching AutoEQ's data convention
- Optional fractional-octave Gaussian smoothing (`--smooth 1/3`, `1/6`, ...)
- Normalization modes: mean (default), median, reference frequency, or none
- Batch conversion with `--output-dir`
- Pure Python standard library, no dependencies

## Install

The script works without installation:

```bash
python rew_to_autoeq/cli.py measurement.txt
```

To install the command line tool:

```bash
pip install git+https://github.com/xup61069/rew-to-autoeq.git
```

This provides the `rew2autoeq` command:

```bash
rew2autoeq measurement.txt
```

## Usage

```bash
rew2autoeq <input.txt> [options]
```

Examples:

```bash
# Basic conversion; writes <input>_autoeq.csv next to the input
rew2autoeq measurement.txt

# Custom output file
rew2autoeq measurement.txt -o my_eq.csv

# 1/3 octave smoothing
rew2autoeq measurement.txt --smooth 1/3

# Normalize so 1 kHz equals 0 dB
rew2autoeq measurement.txt --normalize reference --reference-freq 1000

# Convert every measurement in a folder
rew2autoeq *.txt --output-dir converted/

# Keep the raw absolute SPL values and original frequency resolution
rew2autoeq measurement.txt --no-normalize --no-interpolate
```

## Options

| Option | Description |
| --- | --- |
| `-o, --output` | Output CSV path (single input only) |
| `--output-dir` | Output directory for batch conversion |
| `--smooth OCTAVES` | Fractional-octave smoothing width, e.g. `1/3`, `1/6`, `0.3` |
| `--normalize MODE` | `mean`, `median`, `reference`, or `none` (default: `mean`) |
| `--reference-freq HZ` | Reference frequency for `--normalize reference` |
| `--min-freq HZ` | Lowest frequency kept (default: 20) |
| `--max-freq HZ` | Highest frequency kept (default: 20000) |
| `--steps-per-octave N` | Interpolated grid resolution (default: 20) |
| `--no-interpolate` | Keep the original REW frequency resolution |
| `--quiet` | Print only converted file paths |
| `--version` | Show the version |

## Output Format

The generated CSV has exactly two columns:

```csv
frequency,raw
20.00,0.89
20.71,0.98
...
```

Upload this file to [autoeq.app](https://autoeq.app) to generate parametric EQ settings.

## Exporting From REW

In REW, use **File > Export > Measurement text file** (or the equivalent export option for your version). The default comma-separated export works as-is. No special settings are required.

## Use Case: Pressure-Relief Ear Tips

In-ear monitors (IEMs) with sealed tips can cause uncomfortable pressure buildup in the ear canal. Pressure-relief (vented) ear tips, such as Sancai and Divinus Velvet, solve this by adding a small vent that equalizes air pressure. However, this vent also lets low-frequency sound escape, resulting in noticeable bass loss -- typically 10-20 dB below 200 Hz.

This tool provides a simple pipeline to compensate for that bass leakage:

1. Measure the IEM with vented tips using REW and an IEC 711 coupler.
2. Convert the measurement to AutoEQ format with this tool (`rew2autoeq`).
3. Upload the CSV to [autoeq.app](https://autoeq.app) to generate parametric EQ filters.

### Example

The frequency response below shows the bass loss from a vented tip (note the roll-off below ~200 Hz):

![Vented tip bass loss](docs/examples/vented-tip-bass-loss.png)

After processing with AutoEQ, the generated compensation EQ might look like:

| Filter | Frequency | Q     | Gain   |
|--------|-----------|-------|--------|
| Peaking | 30 Hz   | 0.59  | +9.6 dB |
| Peaking | 30 Hz   | 0.18  | +12.0 dB |
| Peaking | 84 Hz   | 0.18  | +12.0 dB |
| Peaking | 1750 Hz | 1.28  | -11.9 dB |
| Peaking | 6667 Hz | 0.18  | -7.9 dB |

The three low-frequency filters boost the bass back to its original level, while the two high-frequency cuts compensate for resonances introduced by the vent and tip geometry. Your specific values will vary depending on the IEM, tip model, and ear canal coupling -- always measure your own setup.

### Practical Tips

- Use the largest tip size that still seals well. A better seal means less bass leakage to compensate for.
- The vent diameter matters: larger vents relieve pressure better but leak more bass. Finding the right balance is personal.
- Re-measure after swapping tips, even between batches of the same model -- manufacturing tolerances and ear tip aging can shift the response.
- Foam tips can also relieve pressure (they compress and decompress), but they dampen treble differently than silicone vents.

## Development

Run the tests with the standard library test runner:

```bash
python -m unittest discover -s tests -v
```

## Related Work

- [AutoEq](https://github.com/jaakkopasanen/AutoEq) -- Automatic headphone equalization from frequency responses (16k+ stars).
- [REW (Room EQ Wizard)](https://www.roomeqwizard.com/) -- Free room acoustics and audio measurement software.
- [autoeq.app](https://autoeq.app) -- Web-based tool for generating parametric EQ from frequency response CSVs.
- Reddit discussions on IEM pressure and vented tips:
  - [How to alleviate IEM ear pressure -- lack of vents](https://www.reddit.com/r/iems/comments/1kqaea2/) (r/iems)
  - [Who else suffers from IEM pressure issues?](https://www.reddit.com/r/headphones/comments/ubwdab/) (r/headphones)
  - [What is this hole in my earbuds?](https://www.reddit.com/r/headphones/comments/yvwu8v/) (r/headphones)

## License

MIT
