import unittest

from proxgen.layout import compute_layout, page_slots, pick_best_layout


class LayoutTests(unittest.TestCase):
    def test_compute_layout_positive_grid(self):
        layout = compute_layout(page_portrait=False, margin_mm=5.0, gap_mm=3.0)
        self.assertGreaterEqual(layout.cols, 1)
        self.assertGreaterEqual(layout.rows, 1)
        self.assertEqual(layout.per_page, layout.cols * layout.rows)

    def test_compute_layout_negative_margin_raises(self):
        with self.assertRaises(ValueError):
            compute_layout(page_portrait=True, margin_mm=-1.0, gap_mm=3.0)

    def test_pick_best_layout_returns_valid_orientation(self):
        orientation, layout = pick_best_layout(margin_mm=5.0, gap_mm=3.0)
        self.assertIn(orientation, {"portrait", "landscape"})
        self.assertGreater(layout.per_page, 0)

    def test_page_slots_count_matches_per_page(self):
        layout = compute_layout(page_portrait=False, margin_mm=5.0, gap_mm=3.0)
        slots = page_slots(layout)
        self.assertEqual(len(slots), layout.per_page)

    def test_standard_cards_fit_nine_per_portrait_a4_page(self):
        layout = compute_layout(
            page_portrait=True,
            margin_mm=5.0,
            gap_mm=3.0,
            card_w_mm=63.0,
            card_h_mm=88.0,
        )
        self.assertEqual((layout.cols, layout.rows, layout.per_page), (3, 3, 9))

    def test_card_larger_than_available_page_raises(self):
        with self.assertRaises(ValueError):
            compute_layout(
                page_portrait=True,
                margin_mm=5.0,
                gap_mm=3.0,
                card_w_mm=300.0,
                card_h_mm=88.0,
            )


if __name__ == "__main__":
    unittest.main()
