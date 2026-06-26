import unittest

from proxgen.quality import assess_dimensions, preflight_level, quality_level


class QualityTests(unittest.TestCase):
    def test_standard_300_dpi_source_is_adequate_for_cover(self):
        dpi, crop_percent = assess_dimensions(
            width_px=744,
            height_px=1039,
            card_w_mm=63.0,
            card_h_mm=88.0,
            fit="cover",
        )

        self.assertGreaterEqual(dpi, 299.0)
        self.assertLess(crop_percent, 0.1)
        self.assertEqual(quality_level(effective_dpi=dpi, min_dpi=300.0), "OK")

    def test_cover_reports_source_crop(self):
        dpi, crop_percent = assess_dimensions(
            width_px=1000,
            height_px=1000,
            card_w_mm=63.0,
            card_h_mm=88.0,
            fit="cover",
        )

        self.assertAlmostEqual(dpi, 288.6, places=1)
        self.assertGreater(crop_percent, 28.0)

    def test_contain_preserves_the_full_image(self):
        dpi, crop_percent = assess_dimensions(
            width_px=1000,
            height_px=1000,
            card_w_mm=63.0,
            card_h_mm=88.0,
            fit="contain",
        )

        self.assertAlmostEqual(dpi, 403.2, places=1)
        self.assertEqual(crop_percent, 0.0)

    def test_quality_levels(self):
        self.assertEqual(quality_level(effective_dpi=300.0, min_dpi=300.0), "OK")
        self.assertEqual(quality_level(effective_dpi=250.0, min_dpi=300.0), "WARN")
        self.assertEqual(quality_level(effective_dpi=200.0, min_dpi=300.0), "LOW")

    def test_large_cover_crop_is_a_warning_even_with_good_dpi(self):
        self.assertEqual(
            preflight_level(effective_dpi=400.0, crop_percent=20.0, min_dpi=300.0),
            "WARN",
        )


if __name__ == "__main__":
    unittest.main()
