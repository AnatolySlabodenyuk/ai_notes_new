import unittest

from backend.eval_rules import evaluate_generation


class EvalRuleTests(unittest.TestCase):
    def test_generation_fails_when_parent_message_invents_fact(self):
        result = evaluate_generation(
            transcript="Сегодня тренировались звук Р и короткую домашку.",
            history=[],
            generation={
                "internal_note": "Работали со звуком Р.",
                "parent_message": "Ребёнок впервые прочитал целую книгу дома.",
                "history_update": "Есть работа со звуком Р.",
                "qa_suggestions": [],
            },
        )

        self.assertFalse(result.passed)
        self.assertIn("invented", result.failures[0])

    def test_generation_passes_for_grounded_calm_message(self):
        result = evaluate_generation(
            transcript="Сегодня ребёнок повторял звук Р в слогах. Дома повторить 5 слов.",
            history=["На прошлом занятии звук Р получался только с подсказкой."],
            generation={
                "internal_note": "Ребёнок повторял звук Р в слогах, нужна домашняя практика.",
                "parent_message": "Сегодня тренировались произносить звук Р в слогах. Дома можно спокойно повторить 5 слов.",
                "history_update": "Звук Р стал появляться в слогах, сохраняется потребность в практике.",
                "qa_suggestions": ["Продолжить короткую домашнюю практику."],
            },
        )

        self.assertTrue(result.passed, result.failures)


if __name__ == "__main__":
    unittest.main()
