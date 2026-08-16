"""Tests for the core conversion logic."""

import csv
import math
import os
import tempfile
import unittest
from pathlib import Path

from rew_to_autoeq.converter import (
    ConversionError,
    build_log_grid,
    convert_file,
    interpolate_to_grid,
    normalize_response,
    parse_rew_file,
    smooth_response,
    write_autoeq_csv,
)


SAMPLE = Path(__file__).parent / "data" / "sample_rew_export.txt"


class ParseRewFileTests(unittest.TestCase):
    def test_parses_metadata_and_data(self):
        metadata, data = parse_rew_file(SAMPLE)
        self.assertIn("Measurement", metadata)
        self.assertEqual(metadata["Measurement"], "L+R Aug 16")
        self.assertGreaterEqual(len(data), 10)
        self.assertEqual(data[0], (0.366211, 36.488))

    def test_parses_tab_separated_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tabbed.txt"
            path.write_text(
                "Freq(Hz)\tSPL(dB)\tPhase(degrees)\n"
                "20\t100\t1\n"
                "100\t90\t2\n",
                encoding="utf-8",
            )
            _, data = parse_rew_file(path)
            self.assertEqual(data, [(20.0, 100.0), (100.0, 90.0)])

    def test_accepts_files_without_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bare.csv"
            path.write_text("20,100\n100,90\n", encoding="utf-8")
            _, data = parse_rew_file(path)
            self.assertEqual(data, [(20.0, 100.0), (100.0, 90.0)])

    def test_raises_when_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.txt"
            path.write_text("* only comments\n", encoding="utf-8")
            with self.assertRaises(ConversionError):
                parse_rew_file(path)


class GridAndInterpolationTests(unittest.TestCase):
    def test_grid_spans_requested_range(self):
        grid = build_log_grid(20, 20000, 20)
        self.assertAlmostEqual(grid[0], 20)
        self.assertLessEqual(grid[-1], 20000 * 1.0000001)
        self.assertGreater(len(grid), 190)
        self.assertLess(len(grid), 210)

    def test_grid_is_logarithmic(self):
        grid = build_log_grid(100, 200, 20)
        ratios = [grid[i + 1] / grid[i] for i in range(len(grid) - 1)]
        self.assertAlmostEqual(ratios[0], ratios[-1], places=6)

    def test_interpolation_is_log_linear(self):
        data = [(20.0, 0.0), (80.0, 20.0)]
        grid = interpolate_to_grid(data, 20, 80, 1)
        # 40 Hz is exactly the log midpoint between 20 and 80 Hz.
        at_40 = [spl for freq, spl in grid if abs(freq - 40.0) < 1e-9]
        self.assertEqual(len(at_40), 1)
        self.assertAlmostEqual(at_40[0], 10.0, places=9)

    def test_interpolation_clamps_outside_range(self):
        data = [(100.0, 5.0), (1000.0, 10.0)]
        grid = interpolate_to_grid(data, 20, 20000, 5)
        self.assertEqual(grid[0][1], 5.0)
        self.assertEqual(grid[-1][1], 10.0)


class SmoothingAndNormalizationTests(unittest.TestCase):
    def test_smooth_keeps_flat_response_flat(self):
        data = [(freq, 10.0) for freq in range(20, 20001, 100)]
        smoothed = smooth_response(data, 1 / 3)
        self.assertTrue(all(abs(spl - 10.0) < 1e-9 for _, spl in smoothed))

    def test_smooth_reduces_peaks(self):
        data = [
            (250.0, 0.0),
            (500.0, 10.0),
            (1000.0, 20.0),
            (2000.0, 10.0),
            (4000.0, 0.0),
        ]
        smoothed = smooth_response(data, 2)
        peak = max(spl for _, spl in smoothed)
        self.assertLess(peak, 20.0)

    def test_normalize_mean_centers_data(self):
        data = [(20.0, 100.0), (100.0, 110.0), (1000.0, 120.0)]
        normalized = normalize_response(data, "mean")
        self.assertAlmostEqual(sum(spl for _, spl in normalized), 0.0, places=9)

    def test_normalize_median_centers_data(self):
        data = [(20.0, 100.0), (100.0, 110.0), (1000.0, 120.0)]
        normalized = normalize_response(data, "median")
        self.assertEqual(normalized[1][1], 0.0)

    def test_normalize_reference_frequency(self):
        data = [(20.0, 100.0), (1000.0, 108.0), (10000.0, 90.0)]
        normalized = normalize_response(data, "reference", reference_freq=1000)
        self.assertEqual(normalized[1][1], 0.0)

    def test_normalize_none_keeps_absolute_values(self):
        data = [(20.0, 100.1234)]
        normalized = normalize_response(data, "none")
        self.assertEqual(normalized, [(20.0, 100.12)])


class CsvAndConversionTests(unittest.TestCase):
    def test_write_autoeq_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.csv"
            write_autoeq_csv([(20.0, 1.234), (100.0, -5.678)], out)
            with out.open(encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["frequency", "raw"])
            self.assertEqual(rows[1], ["20.00", "1.23"])
            self.assertEqual(rows[2], ["100.00", "-5.68"])

    def test_convert_file_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "converted.csv"
            result = convert_file(SAMPLE, out)
            self.assertTrue(out.exists())
            self.assertIn("points", result)
            with out.open(encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["frequency", "raw"])
            self.assertEqual(len(rows) - 1, len(result["points"]))
            # Every value should be rounded to two decimals.
            for _, raw in rows[1:]:
                self.assertEqual(len(raw.split(".")[1]), 2)

    def test_convert_file_respects_frequency_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "converted.csv"
            result = convert_file(
                SAMPLE, out, min_freq=100, max_freq=10000, steps_per_octave=1
            )
            freqs = [freq for freq, _ in result["points"]]
            self.assertGreaterEqual(freqs[0], 100)
            self.assertLessEqual(freqs[-1], 10000)

    def test_convert_file_raises_without_points_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "converted.csv"
            with self.assertRaises(ConversionError):
                convert_file(SAMPLE, out, min_freq=100000, max_freq=200000)


if __name__ == "__main__":
    unittest.main()
