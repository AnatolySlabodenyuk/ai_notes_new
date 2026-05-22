import unittest
from pathlib import Path


class FrontendStaticSafetyTests(unittest.TestCase):
    def test_app_does_not_render_model_or_store_data_with_inner_html(self):
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertNotIn(".innerHTML", app)


if __name__ == "__main__":
    unittest.main()
