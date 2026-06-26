import tempfile
import unittest
from pathlib import Path

from proxgen.card_formats import CARD_FORMATS, get_card_format
from proxgen.cli import parse_args_with_config, resolve_card_dimensions_mm


class CardFormatTests(unittest.TestCase):
    def test_standard_dimensions_in_portrait(self):
        orientation, width_mm, height_mm = resolve_card_dimensions_mm(
            card_format=get_card_format("standard"),
            card_orientation="portrait",
            fronts=[],
        )

        self.assertEqual(orientation, "portrait")
        self.assertEqual((width_mm, height_mm), (63.0, 88.0))

    def test_auto_orientation_without_images_defaults_to_portrait(self):
        orientation, width_mm, height_mm = resolve_card_dimensions_mm(
            card_format=get_card_format("planechase"),
            card_orientation="auto",
            fronts=[],
        )

        self.assertEqual(orientation, "portrait")
        self.assertEqual((width_mm, height_mm), (88.0, 126.0))

    def test_cli_accepts_standard_card_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text("{}", encoding="utf-8")

            args = parse_args_with_config(["--config", str(config_path), "--card-format", "standard"])

        self.assertEqual(args.card_format, "standard")

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            get_card_format("oversized")

    def test_supported_format_names_are_stable(self):
        self.assertEqual(set(CARD_FORMATS), {"planechase", "standard"})


if __name__ == "__main__":
    unittest.main()
