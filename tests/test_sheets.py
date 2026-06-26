import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader

from proxgen.sheets import generate_repeated_front_sheet


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOBLIN_TOKEN = PROJECT_ROOT / "goblin_token_mtg_clean_clear_red_63x88mm_300dpi.jpg"


class RepeatedSheetTests(unittest.TestCase):
    def test_goblin_token_generates_nine_standard_cards_on_one_a4_page(self):
        self.assertTrue(GOBLIN_TOKEN.exists(), "Goblin token test image is missing")

        with Image.open(GOBLIN_TOKEN) as image:
            self.assertEqual(image.size, (744, 1039))
            self.assertEqual(image.info.get("dpi"), (300, 300))

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "goblin_token_sheet.pdf"
            result = generate_repeated_front_sheet(
                image_path=GOBLIN_TOKEN,
                out_pdf=output,
                copies=9,
                gap_mm=0.2,
                margin_mm=0.0,
                card_w_mm=63.0,
                card_h_mm=88.0,
            )
            reader = PdfReader(str(output))

        self.assertEqual(result.page_orientation, "portrait")
        self.assertEqual(result.layout.per_page, 9)
        self.assertEqual(result.pages, 1)
        self.assertEqual(len(reader.pages), 1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.28, places=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.89, places=1)


if __name__ == "__main__":
    unittest.main()
