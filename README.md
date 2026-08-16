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

## Development

Run the tests with the standard library test runner:

```bash
python -m unittest discover -s tests -v
```

## License

MIT
