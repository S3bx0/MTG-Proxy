import unittest

from gui_app import build_common_args, create_app, normalize_output_name


class GuiArgumentTests(unittest.TestCase):
    def test_standard_format_is_forwarded_to_cli(self):
        args = build_common_args({"out_name": "standard.pdf", "card_format": "standard"})

        self.assertIn("--card-format", args)
        self.assertEqual(args[args.index("--card-format") + 1], "standard")

    def test_output_name_rejects_directories(self):
        for output_name in ("../outside.pdf", "C:outside.pdf"):
            with self.subTest(output_name=output_name):
                with self.assertRaises(ValueError):
                    normalize_output_name(output_name)

    def test_output_name_requires_pdf_extension(self):
        with self.assertRaises(ValueError):
            normalize_output_name("outside.txt")

    def test_run_requires_a_csrf_token(self):
        app = create_app()
        client = app.test_client()

        response = client.post("/run", data={"action": "dry_run", "out_name": "test.pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Nieprawidłowy token bezpieczeństwa", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
