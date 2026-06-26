import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader

from proxgen.render import generate_pdf


class RenderTests(unittest.TestCase):
    def _make_image(self, path: Path, color: tuple[int, int, int]) -> None:
        image = Image.new("RGB", (900, 1260), color)
        image.save(path)

    def test_standard_cards_generate_a_duplex_a4_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fronts = [root / f"front_{index}.png" for index in range(2)]
            back = root / "back.png"
            output = root / "standard.pdf"

            for front in fronts:
                self._make_image(front, (180, 40, 40))
            self._make_image(back, (40, 40, 180))

            generate_pdf(
                front_paths=fronts,
                back_paths=[back],
                out_pdf=output,
                page_portrait=True,
                margin_mm=5.0,
                gap_mm=3.0,
                fit="cover",
                duplex_mode="paired",
                back_pairing="smart",
                back_transform="rotate180",
                back_placement="mirror-x",
                card_w_mm=63.0,
                card_h_mm=88.0,
            )

            reader = PdfReader(str(output))

        self.assertEqual(len(reader.pages), 2)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.28, places=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.89, places=1)


if __name__ == "__main__":
    unittest.main()
