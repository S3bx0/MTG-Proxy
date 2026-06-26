import tempfile
import unittest
from pathlib import Path

from PIL import Image

from proxgen.pairing import (
    append_rename_history_entry,
    apply_strict_rename_plan,
    build_back_list,
    build_powershell_rename_script,
    build_strict_rename_plan,
    undo_last_rename_batch,
)


class PairingTests(unittest.TestCase):
    def _mk_png(self, path: Path, size=(100, 100), color=(255, 0, 0)):
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", size, color)
        img.save(path)

    def test_single_back_reused_for_all_fronts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "front_a.png"
            f2 = root / "front_b.png"
            b1 = root / "back.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)

            result = build_back_list([f1, f2], [b1], back_pairing="smart")
            self.assertEqual(result, [b1, b1])

    def test_strict_pairing_matches_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "Beta_rewers.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            result = build_back_list([f1, f2], [b1, b2], back_pairing="strict")
            self.assertEqual(result, [b1, b2])

    def test_strict_pairing_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "Gamma_back.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            with self.assertRaises(ValueError):
                build_back_list([f1, f2], [b1, b2], back_pairing="strict")

    def test_invalid_pairing_mode_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "a.png"
            b1 = root / "b.png"
            self._mk_png(f1)
            self._mk_png(b1)

            with self.assertRaises(ValueError):
                build_back_list([f1], [b1, b1], back_pairing="invalid")

    def test_build_strict_rename_plan_suggests_target_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "random_name.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            plan = build_strict_rename_plan([f1, f2], [b1, b2])
            self.assertEqual(plan.already_matched, 1)
            self.assertEqual(plan.missing_fronts, [])
            self.assertEqual(len(plan.suggestions), 1)
            self.assertEqual(plan.suggestions[0].source.name, "random_name.png")
            self.assertEqual(plan.suggestions[0].target_name, "Beta_back.png")

    def test_build_powershell_rename_script_contains_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "random_name.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            plan = build_strict_rename_plan([f1, f2], [b1, b2])
            script = build_powershell_rename_script(plan=plan, back_dir=root)
            self.assertIn("Rename-Item", script)
            self.assertIn("random_name.png", script)
            self.assertIn("Beta_back.png", script)

    def test_apply_strict_rename_plan_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "random_name.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            plan = build_strict_rename_plan([f1, f2], [b1, b2])

            dry = apply_strict_rename_plan(plan=plan, back_dir=root, apply_changes=False)
            self.assertTrue(dry.dry_run)
            self.assertEqual(dry.applied, 0)
            self.assertEqual(len(dry.actions), 1)
            self.assertTrue((root / "random_name.png").exists())

            applied = apply_strict_rename_plan(plan=plan, back_dir=root, apply_changes=True)
            self.assertFalse(applied.dry_run)
            self.assertEqual(applied.applied, 1)
            self.assertTrue((root / "Beta_back.png").exists())
            self.assertFalse((root / "random_name.png").exists())

    def test_undo_last_rename_batch_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "rename_history.jsonl"

            f1 = root / "Alpha.png"
            f2 = root / "Beta.png"
            b1 = root / "Alpha_back.png"
            b2 = root / "random_name.png"
            self._mk_png(f1)
            self._mk_png(f2)
            self._mk_png(b1)
            self._mk_png(b2)

            plan = build_strict_rename_plan([f1, f2], [b1, b2])
            applied = apply_strict_rename_plan(plan=plan, back_dir=root, apply_changes=True)
            self.assertEqual(applied.applied, 1)

            append_rename_history_entry(history_path=history, back_dir=root, actions=applied.actions)
            self.assertTrue(history.exists())

            undo_preview = undo_last_rename_batch(history_path=history, back_dir=root, apply_changes=False)
            self.assertTrue(undo_preview.dry_run)
            self.assertFalse(undo_preview.no_history)
            self.assertEqual(len(undo_preview.actions), 1)
            self.assertTrue((root / "Beta_back.png").exists())

            undo_apply = undo_last_rename_batch(history_path=history, back_dir=root, apply_changes=True)
            self.assertFalse(undo_apply.dry_run)
            self.assertEqual(undo_apply.applied, 1)
            self.assertTrue((root / "random_name.png").exists())
            self.assertFalse((root / "Beta_back.png").exists())
            self.assertFalse(history.exists())


if __name__ == "__main__":
    unittest.main()
