"""REW 轉 AutoEQ 轉換器的指令列介面。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from rew_to_autoeq import __version__
from rew_to_autoeq.converter import ConversionError, convert_file


def _parse_fraction(value: str) -> float:
    """解析平滑寬度，例如 '1/3'、'1/6'、'2/3' 或 '0.3'。"""
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
            f"無效的分數值：{value!r}（預期例如 '1/3'、'1/6'、'0.3'）"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rew2autoeq",
        description="把 REW（Room EQ Wizard）的量測匯出檔轉成 AutoEQ 可讀取的 CSV。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
範例：
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
        help="一個或多個 REW 量測文字檔。",
    )
    parser.add_argument(
        "-o", "--output",
        help="輸出 CSV 路徑（只能搭配單一輸入檔使用）。",
    )
    parser.add_argument(
        "--output-dir",
        help="轉換檔案的輸出資料夾；檔名預設為 <名稱>_autoeq.csv。",
    )
    parser.add_argument(
        "--smooth",
        type=_parse_fraction,
        metavar="OCTAVES",
        help="以倍頻程為單位的平滑寬度，例如 1/3、1/6 或 0.3（預設：不平滑）。",
    )
    parser.add_argument(
        "--normalize",
        choices=("mean", "median", "reference", "none"),
        default="mean",
        help="SPL 正規化模式（預設：mean）。",
    )
    parser.add_argument(
        "--reference-freq",
        type=float,
        metavar="HZ",
        help="搭配 --normalize reference 使用的參考頻率（Hz）。",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=20,
        help="保留的最低頻率（Hz，預設：20）。",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=20000,
        help="保留的最高頻率（Hz，預設：20000）。",
    )
    parser.add_argument(
        "--steps-per-octave",
        type=int,
        default=20,
        metavar="N",
        help="內插格點解析度（預設：20）。",
    )
    parser.add_argument(
        "--no-interpolate",
        action="store_true",
        help="保留 REW 原始頻率解析度。",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只印出錯誤與最終輸出路徑。",
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
        parser.error("--output 只能搭配單一輸入檔使用")
    if args.normalize == "reference" and args.reference_freq is None:
        parser.error("--normalize reference 需要搭配 --reference-freq")

    input_paths = [Path(p) for p in args.inputs]
    missing = [p for p in input_paths if not p.exists()]
    if missing:
        parser.error("找不到輸入檔：" + str(missing[0]))

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
            _print(f"處理中：{input_path}")
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
                f"  {len(points)} 個資料點 "
                f"（相對 dB 範圍 {min(spls):.1f} 至 {max(spls):.1f}）"
            )
            _print(f"已儲存：{output_path}")
        except (ConversionError, OSError, ValueError) as exc:
            print(f"錯誤：{input_path}: {exc}", file=sys.stderr)
            return 1
        output_paths.append(output_path)

    print("完成！把 CSV 上傳到 https://autoeq.app 即可產生 parametric EQ。")
    if args.quiet:
        for path in output_paths:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())