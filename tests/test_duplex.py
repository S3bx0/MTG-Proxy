import unittest

from proxgen.duplex import back_slot_map, resolve_back_placement


class DuplexTests(unittest.TestCase):
    def test_back_slot_map_same(self):
        self.assertEqual(back_slot_map(cols=2, rows=2, placement="same"), [0, 1, 2, 3])

    def test_back_slot_map_mirror_x(self):
        self.assertEqual(back_slot_map(cols=2, rows=2, placement="mirror-x"), [1, 0, 3, 2])

    def test_back_slot_map_mirror_y(self):
        self.assertEqual(back_slot_map(cols=2, rows=2, placement="mirror-y"), [2, 3, 0, 1])

    def test_back_slot_map_rotate180(self):
        self.assertEqual(back_slot_map(cols=2, rows=2, placement="rotate180"), [3, 2, 1, 0])

    def test_resolve_back_placement_auto(self):
        self.assertEqual(resolve_back_placement(back_placement="auto", page_portrait=True), "mirror-x")
        self.assertEqual(resolve_back_placement(back_placement="auto", page_portrait=False), "mirror-y")

    def test_resolve_back_placement_invalid(self):
        with self.assertRaises(ValueError):
            resolve_back_placement(back_placement="bad", page_portrait=True)


if __name__ == "__main__":
    unittest.main()
