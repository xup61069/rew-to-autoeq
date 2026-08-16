"""指令列介面的測試。"""

import tempfile
import unittest
from pathlib import Path

from rew_to_autoeq.cli import _parse_fraction, main


SAMPLE = Path(__file__).parent / "data" / "sample_rew_export.txt"


class ParseFractionTests(unittest.TestCase):
    def test_fractions(self):
        self.assertEqual(_parse_fraction("1/3"), 1 / 3)
        self.assertEqual(_parse_fraction("1/6"), 1 / 6)
        self.assertEqual(_parse_fraction("2/3"), 2 / 3)

    def test_decimals(self):
        self.assertEqual(_parse_fraction("0.3"), 0.3)
        self.assertEqual(_parse_fraction("1"), 1.0)


class CliTests(unittest.TestCase):
    def test_convert_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.csv"
            code = main([str(SAMPLE), "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

    def test_convert_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            code = main([str(SAMPLE), "--output-dir", str(out_dir)])
            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "sample_rew_export_autoeq.csv").exists())

    def test_convert_with_smoothing_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.csv"
            code = main(
                [
                    str(SAMPLE),
                    "-o",
                    str(out),
                    "--smooth",
                    "1/3",
                    "--normalize",
                    "reference",
                    "--reference-freq",
                    "1000",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

    def test_missing_input_returns_error(self):
        with self.assertRaises(SystemExit):
            main(["does-not-exist.txt"])

    def test_output_with_multiple_inputs_returns_error(self):
        with self.assertRaises(SystemExit):
            main([str(SAMPLE), str(SAMPLE), "-o", "out.csv"])


if __name__ == "__main__":
    unittest.main()
