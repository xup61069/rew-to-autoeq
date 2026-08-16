"""把 REW 匯出檔轉成 AutoEQ CSV 的核心轉換邏輯。"""

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
    """REW 檔無法解析或轉換時拋出的例外。"""


def _decode_text(path: Path) -> str:
    """解碼量測檔，依序嘗試常見的編碼。"""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "big5", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _split_row(line: str) -> List[str]:
    """切分 REW 的一列資料，支援逗號、分號、Tab 與空白分隔的匯出檔。"""
    if "\t" in line:
        return [cell.strip() for cell in line.split("\t")]
    if ";" in line:
        return [cell.strip() for cell in line.split(";")]
    if "," in line:
        return [cell.strip() for cell in line.split(",")]
    return line.split()


def _looks_like_header(line: str) -> bool:
    """第一個欄位是文字而非數字時，回傳 True。"""
    cells = _split_row(line)
    if not cells:
        return False
    try:
        float(cells[0])
    except ValueError:
        return True
    return False


def _parse_header(line: str) -> Dict[str, int]:
    """在標題列中找出頻率與 SPL 欄位的位置。"""
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
        raise ConversionError(f"無法在標題列中找出頻率/SPL 欄位：{line}")
    return {"freq": freq_col, "spl": mag_col}


def parse_rew_file(
    path: str | Path,
) -> Tuple[Dict[str, str], List[Tuple[float, float]]]:
    """把 REW 文字匯出檔解析成中繼資料與 (頻率, SPL) 資料對。

    REW 的註解行以 ``*`` 開頭，資料列通常是
    ``Freq(Hz), SPL(dB), Phase(degrees)``。沒有標題列的檔案也能接受，
    此時直接使用前兩個欄位。

    Returns:
        回傳 ``(metadata, data)``，其中 metadata 是註解標題欄位的字典，
        data 是 ``(freq_hz, spl_db)`` 元組的列表。
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
        raise ConversionError(f"在 {path} 中找不到頻率響應資料")
    return metadata, data


def build_log_grid(
    start_freq: float, end_freq: float, steps_per_octave: int = 20
) -> List[float]:
    """從 ``start_freq`` 到 ``end_freq`` 建立對數間隔的頻率格點。"""
    if start_freq <= 0 or end_freq <= start_freq:
        raise ValueError("start_freq 必須為正數，且 end_freq 必須大於 start_freq")
    if steps_per_octave <= 0:
        raise ValueError("steps_per_octave 必須為正數")

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
    """把響應資料內插到對數間隔的頻率格點上。

    在對數頻率空間中做線性內插，這是音訊量測資料的自然內插方式。
    超出量測範圍的點會固定在最接近的量測值。
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
    """對響應曲線套用分數倍頻程高斯平滑。"""
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


def _interpolate_at(data: Sequence[Tuple[float, float]], freq: float) -> float:
    """在對數頻率空間中，於單一頻率做線性內插；超出量測範圍時取最近的量測值。"""
    points = sorted(data, key=lambda p: p[0])
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    idx = bisect.bisect_left(xs, freq)
    if idx == 0:
        return ys[0]
    if idx == len(xs):
        return ys[-1]
    if xs[idx] == freq:
        return ys[idx]
    x0, y0 = xs[idx - 1], ys[idx - 1]
    x1, y1 = xs[idx], ys[idx]
    t = (math.log10(freq) - math.log10(x0)) / (math.log10(x1) - math.log10(x0))
    return y0 + t * (y1 - y0)


def normalize_response(
    data: Sequence[Tuple[float, float]],
    mode: str = "mean",
    reference_freq: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """把 SPL 數值正規化成相對 dB。

    支援的模式：
    - ``mean``：以平均 SPL 為中心（預設）。
    - ``median``：以中位數 SPL 為中心。
    - ``reference``：把 ``reference_freq`` 設為 0 dB（以對數空間線性內插計算）。
    - ``none``：保留絕對 SPL 數值不變。
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
            raise ValueError("normalize=reference 需要指定 reference_freq")
        if reference_freq <= 0:
            raise ValueError("reference_freq 必須為正數")
        offset = _interpolate_at(data, reference_freq)
    else:
        raise ValueError(f"未知的正規化模式：{mode}")

    return [(freq, round(spl - offset, 2)) for freq, spl in data]


def write_autoeq_csv(
    data: Sequence[Tuple[float, float]], output_path: str | Path
) -> None:
    """以 AutoEQ 可讀取的 CSV 格式寫出響應資料。"""
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
    """把單一 REW 匯出檔轉成 AutoEQ 格式。

    Returns:
        一個包含中繼資料、轉換後的資料點、輸入與輸出路徑的字典。
    """
    metadata, data = parse_rew_file(input_path)
    data = [(freq, spl) for freq, spl in data if min_freq <= freq <= max_freq]
    if not data:
        raise ConversionError(
            f"在 {min_freq:g} Hz 到 {max_freq:g} Hz 之間找不到任何資料點"
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