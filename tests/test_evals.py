import unittest

from backend.eval_rules import evaluate_generation


class EvalRuleTests(unittest.TestCase):
    def test_generation_fails_when_parent_blocks_invent_fact(self):
        result = evaluate_generation(
            transcript="Сегодня тренировались звук Р и короткую домашку.",
            history=[],
            generation={
                "what_we_did": "Работали со звуком Р.",
                "what_changed": "Ребёнок впервые прочитал целую книгу дома.",
                "home_practice": "Есть работа со звуком Р.",
            },
        )

        self.assertFalse(result.passed)
        self.assertIn("invented", result.failures[0])

    def test_generation_fails_when_it_uses_history_as_current_session_fact(self):
        result = evaluate_generation(
            transcript="Сегодня проходили алфавит и учились звонить по телефону.",
            history=["На прошлом занятии ребёнок работал со звуком Р."],
            generation={
                "what_we_did": "Работали со звуком Р и проходили алфавит.",
                "what_changed": "Учились звонить по телефону.",
                "home_practice": "Специалист не указал домашнюю практику.",
            },
        )

        self.assertFalse(result.passed)
        self.assertIn("invented", result.failures[0])

    def test_generation_passes_for_grounded_calm_message(self):
        result = evaluate_generation(
            transcript="Сегодня ребёнок повторял звук Р в слогах. Дома повторить 5 слов.",
            history=["На прошлом занятии звук Р получался только с подсказкой."],
            generation={
                "what_we_did": "Сегодня тренировались произносить звук Р в слогах.",
                "what_changed": "Звук Р стал появляться в слогах, сохраняется потребность в практике.",
                "home_practice": "Дома можно спокойно повторить 5 слов.",
            },
        )

        self.assertTrue(result.passed, result.failures)


if __name__ == "__main__":
    unittest.main()
