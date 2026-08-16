"""Core conversion logic for turning REW exports into AutoEQ CSVs."""

from __future__ import annotations

import bisect
import csv
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ConversionError",
    "AUTOEQ_HEADER",
    "build_log_grid",
    "convert_file",
    "interpolate_to_grid",
    "normalize_response",
    "parse_rew_file",
    "smooth_response",
    "write_autoeq_csv",
]


AUTOEQ_HEADER = ("frequency", "raw")


class ConversionError(ValueError):
    """Raised when a REW file cannot be parsed or converted."""


def _decode_text(path: Path) -> str:
    """Decode a measurement file, trying common encodings in order."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "big5", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _split_row(line: str) -> List[str]:
    """Split a REW row, supporting comma and tab separated exports."""
    if "\t" in line:
        return [cell.strip() for cell in line.split("\t")]
    return [cell.strip() for cell in line.split(",")]


def _looks_like_header(line: str) -> bool:
    """Return True when the first cell is text rather than a number."""
    cells = _split_row(line)
    if not cells:
        return False
    try:
        float(cells[0])
    except ValueError:
        return True
    return False


def _parse_header(line: str) -> Dict[str, int]:
    """Locate the frequency and SPL columns in a header row."""
    indices: Dict[str, int] = {}
    for i, cell in enumerate(_split_row(line)):
        key = cell.lower()
        key = re.sub(r"\s*\(.*?\)", "", key).strip()
        indices.setdefault(key, i)

    freq_col = indices.get("freq")
    if freq_col is None:
        freq_col = indices.get("frequency")
    mag_col = None
    for candidate in ("spl", "db", "magnitude", "mag", "level", "response", "raw"):
        if candidate in indices:
            mag_col = indices[candidate]
            break

    if freq_col is None or mag_col is None:
        raise ConversionError(f"Could not identify frequency/SPL columns in header: {line}")
    return {"freq": freq_col, "spl": mag_col}


def parse_rew_file(
    path: str | Path,
) -> Tuple[Dict[str, str], List[Tuple[float, float]]]:
    """Parse a REW text export into metadata and (frequency, SPL) pairs.

    REW comment lines start with ``*`` and data rows are normally
    ``Freq(Hz), SPL(dB), Phase(degrees)``. Files without a header row are
    also accepted, in which case the first two columns are used.

    Returns:
        Tuple of ``(metadata, data)`` where metadata is a dict of comment
        header fields and data is a list of ``(freq_hz, spl_db)`` tuples.
    """
    text = _decode_text(Path(path))
    metadata: Dict[str, str] = {}
    data: List[Tuple[float, float]] = []
    header: Optional[Dict[str, int]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("*"):
            content = line[1:].strip()
            if ":" in content:
                key, _, value = content.partition(":")
                metadata[key.strip()] = value.strip()
            continue

        if header is None:
            if _looks_like_header(line):
                header = _parse_header(line)
            else:
                header = {"freq": 0, "spl": 1}

        parts = _split_row(line)
        if len(parts) <= max(header.values()):
            continue
        try:
            freq = float(parts[header["freq"]])
            spl = float(parts[header["spl"]])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(freq) and math.isfinite(spl):
            data.append((freq, spl))

    if not data:
        raise ConversionError(f"No frequency response data found in {path}")
    return metadata, data


def build_log_grid(
    start_freq: float, end_freq: float, steps_per_octave: int = 20
) -> List[float]:
    """Build a log-spaced frequency grid from ``start_freq`` to ``end_freq``."""
    if start_freq <= 0 or end_freq <= start_freq:
        raise ValueError("start_freq must be positive and end_freq must be larger")
    if steps_per_octave <= 0:
        raise ValueError("steps_per_octave must be positive")

    freqs: List[float] = []
    f = float(start_freq)
    factor = 2.0 ** (1.0 / steps_per_octave)
    while f <= end_freq * (1.0 + 1e-9):
        freqs.append(f)
        f *= factor
    return freqs


def interpolate_to_grid(
    data: Sequence[Tuple[float, float]],
    start_freq: float = 20,
    end_freq: float = 20000,
    steps_per_octave: int = 20,
) -> List[Tuple[float, float]]:
    """Interpolate response points onto a log-spaced frequency grid.

    Values are linearly interpolated in log-frequency space, which is the
    natural interpolation for audio measurement data. Points outside the
    measured range are clamped to the nearest measured value.
    """
    if not data:
        return []

    points = sorted(data, key=lambda p: p[0])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    result: List[Tuple[float, float]] = []

    for target in build_log_grid(start_freq, end_freq, steps_per_octave):
        idx = bisect.bisect_left(xs, target)
        if idx == 0:
            spl = ys[0]
        elif idx == len(xs):
            spl = ys[-1]
        elif xs[idx] == target:
            spl = ys[idx]
        else:
            x0, y0 = xs[idx - 1], ys[idx - 1]
            x1, y1 = xs[idx], ys[idx]
            t = (math.log10(target) - math.log10(x0)) / (
                math.log10(x1) - math.log10(x0)
            )
            spl = y0 + t * (y1 - y0)
        result.append((target, spl))

    return result


def smooth_response(
    data: Sequence[Tuple[float, float]], octaves: float = 1.0 / 3.0
) -> List[Tuple[float, float]]:
    """Apply fractional-octave Gaussian smoothing to a response curve."""
    if octaves <= 0:
        return list(data)

    result: List[Tuple[float, float]] = []
    half_width = 2.0 ** (octaves / 2.0)
    for freq, spl in data:
        f_low = freq / half_width
        f_high = freq * half_width
        total_s = 0.0
        total_w = 0.0
        for other_freq, other_spl in data:
            if f_low <= other_freq <= f_high:
                log_ratio = math.log2(other_freq / freq) / (octaves / 2.0)
                weight = math.exp(-0.5 * log_ratio * log_ratio)
                total_s += other_spl * weight
                total_w += weight
        result.append((freq, total_s / total_w if total_w else spl))
    return result


def normalize_response(
    data: Sequence[Tuple[float, float]],
    mode: str = "mean",
    reference_freq: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """Normalize SPL values into relative dB.

    Supported modes:
    - ``mean``: center the response on the average SPL (default).
    - ``median``: center the response on the median SPL.
    - ``reference``: set the nearest point to ``reference_freq`` to 0 dB.
    - ``none``: keep absolute SPL values unchanged.
    """
    if mode == "none":
        return [(freq, round(spl, 2)) for freq, spl in data]
    if not data:
        return list(data)

    values = [spl for _, spl in data]
    if mode == "mean":
        offset = sum(values) / len(values)
    elif mode == "median":
        ordered = sorted(values)
        n = len(ordered)
        if n % 2:
            offset = ordered[n // 2]
        else:
            offset = (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    elif mode == "reference":
        if reference_freq is None:
            raise ValueError("normalize=reference requires reference_freq")
        offset = min(data, key=lambda p: abs(p[0] - reference_freq))[1]
    else:
        raise ValueError(f"Unknown normalization mode: {mode}")

    return [(freq, round(spl - offset, 2)) for freq, spl in data]


def write_autoeq_csv(
    data: Sequence[Tuple[float, float]], output_path: str | Path
) -> None:
    """Write response data in the CSV format AutoEQ reads."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(AUTOEQ_HEADER)
        for freq, spl in data:
            writer.writerow([f"{freq:.2f}", f"{spl:.2f}"])


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    min_freq: float = 20,
    max_freq: float = 20000,
    steps_per_octave: int = 20,
    smooth_octaves: Optional[float] = None,
    normalize: str = "mean",
    reference_freq: Optional[float] = None,
    interpolate: bool = True,
) -> Dict[str, object]:
    """Convert a single REW export to AutoEQ format.

    Returns:
        A dict with metadata, the converted points, and input/output paths.
    """
    metadata, data = parse_rew_file(input_path)
    data = [(freq, spl) for freq, spl in data if min_freq <= freq <= max_freq]
    if not data:
        raise ConversionError(
            f"No data points found between {min_freq:g} Hz and {max_freq:g} Hz"
        )

    if interpolate:
        data = interpolate_to_grid(data, min_freq, max_freq, steps_per_octave)
    if smooth_octaves:
        data = smooth_response(data, smooth_octaves)
    data = normalize_response(data, normalize, reference_freq)

    write_autoeq_csv(data, output_path)
    return {
        "metadata": metadata,
        "points": data,
        "input": str(input_path),
        "output": str(output_path),
    }
