import unittest
from pathlib import Path


class FrontendStaticSafetyTests(unittest.TestCase):
    def test_app_does_not_render_model_or_store_data_with_inner_html(self):
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertNotIn(".innerHTML", app)

    def test_parent_mode_copy_and_admin_mode_copy_are_present(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertIn("Демо-режим", html)
        self.assertIn("Специалист / админ", html)
        self.assertIn("Родитель", html)
        self.assertIn("renderParentMode", app)
        self.assertIn("renderAdminMode", app)

    def test_frontend_uses_parent_facing_session_fields(self):
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertIn("what_we_did", app)
        self.assertIn("what_changed", app)
        self.assertIn("home_practice", app)
        self.assertNotIn("internalNote", app)

    def test_parent_mode_does_not_render_ai_question_chat(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertNotIn("questionInput", html)
        self.assertNotIn("askBtn", html)
        self.assertNotIn("answerBox", html)
        self.assertNotIn("/api/ask-history", app)

    def test_add_child_form_and_api_calls_are_present(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        app = Path("frontend/app.js").read_text(encoding="utf-8")

        self.assertIn('<details class="add-child-disclosure" id="addChildDisclosure">', html)
        self.assertIn('<summary class="add-child-summary">+ Добавить ребёнка</summary>', html)
        self.assertIn("childNameInput", html)
        self.assertIn("childAgeInput", html)
        self.assertIn("childFocusInput", html)
        self.assertIn("childGoalsInput", html)
        self.assertIn("addChildBtn", html)
        self.assertIn('const addChildDisclosure = $("addChildDisclosure");', app)
        self.assertIn("addChildDisclosure.open = false;", app)
        self.assertIn('$("childNameInput").focus();', app)
        self.assertIn('api("/api/children"', app)
        self.assertIn("method: \"POST\"", app)
        self.assertIn("/api/reset-child", app)
        self.assertNotIn('api("/api/reset", {method: "POST"', app)


if __name__ == "__main__":
    unittest.main()
