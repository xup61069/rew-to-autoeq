"""Command line interface for the REW to AutoEQ converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from rew_to_autoeq import __version__
from rew_to_autoeq.converter import ConversionError, convert_file


def _parse_fraction(value: str) -> float:
    """Parse smoothing values like '1/3', '1/6', '2/3' or '0.3'."""
    text = value.strip()
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            pass
    try:
        return float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid fractional value: {value!r} (expected e.g. '1/3', '1/6', '0.3')"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rew2autoeq",
        description="Convert REW (Room EQ Wizard) measurement exports into "
        "CSV files that AutoEQ can read.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  rew2autoeq measurement.txt
  rew2autoeq measurement.txt -o my_eq.csv
  rew2autoeq measurement.txt --smooth 1/3
  rew2autoeq measurement.txt --normalize reference --reference-freq 1000
  rew2autoeq *.txt --output-dir converted/
""",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more REW measurement text files.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output CSV path (only valid with a single input file).",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for converted files; names default to <name>_autoeq.csv.",
    )
    parser.add_argument(
        "--smooth",
        type=_parse_fraction,
        metavar="OCTAVES",
        help="Smoothing width in octaves, e.g. 1/3, 1/6 or 0.3 (default: none).",
    )
    parser.add_argument(
        "--normalize",
        choices=("mean", "median", "reference", "none"),
        default="mean",
        help="SPL normalization mode (default: mean).",
    )
    parser.add_argument(
        "--reference-freq",
        type=float,
        metavar="HZ",
        help="Reference frequency in Hz for --normalize reference.",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=20,
        help="Lowest frequency kept in Hz (default: 20).",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=20000,
        help="Highest frequency kept in Hz (default: 20000).",
    )
    parser.add_argument(
        "--steps-per-octave",
        type=int,
        default=20,
        metavar="N",
        help="Interpolated grid resolution (default: 20).",
    )
    parser.add_argument(
        "--no-interpolate",
        action="store_true",
        help="Keep the original REW frequency resolution.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors and the final output paths.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _print(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.output and len(args.inputs) > 1:
        parser.error("--output can only be used with a single input file")
    if args.normalize == "reference" and args.reference_freq is None:
        parser.error("--normalize reference requires --reference-freq")

    input_paths = [Path(p) for p in args.inputs]
    missing = [p for p in input_paths if not p.exists()]
    if missing:
        parser.error("input file not found: " + str(missing[0]))

    output_paths: List[Path] = []
    for input_path in input_paths:
        if args.output:
            output_path = Path(args.output)
        elif args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{input_path.stem}_autoeq.csv"
        else:
            output_path = input_path.with_name(f"{input_path.stem}_autoeq.csv")

        try:
            _print(f"Processing: {input_path}")
            result = convert_file(
                input_path,
                output_path,
                min_freq=args.min_freq,
                max_freq=args.max_freq,
                steps_per_octave=args.steps_per_octave,
                smooth_octaves=args.smooth,
                normalize=args.normalize,
                reference_freq=args.reference_freq,
                interpolate=not args.no_interpolate,
            )
            points = result["points"]
            assert isinstance(points, list)
            spls = [spl for _, spl in points]
            _print(
                f"  {len(points)} points "
                f"({min(spls):.1f} to {max(spls):.1f} dB relative)"
            )
            _print(f"Saved: {output_path}")
        except (ConversionError, OSError, ValueError) as exc:
            print(f"Error: {input_path}: {exc}", file=sys.stderr)
            return 1
        output_paths.append(output_path)

    print("Done! Upload the CSV to https://autoeq.app to generate parametric EQ.")
    if args.quiet:
        for path in output_paths:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
