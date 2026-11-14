# ПРИКЛАД-ЧЕРНЕТКА тесту модуля td_<галузь>_elearning (звірити імена моделей/полів з вихідниками 19.0).
from odoo.tests.common import TransactionCase

ROLES = 3  # = кількість ролей у package/docs/user-guide (admin.md включно); підставити з INDEX A-16b


class TestElearning(TransactionCase):
    def test_courses_per_role(self):
        courses = self.env["slide.channel"].search([("name", "like", "Курс:")])
        self.assertEqual(len(courses), ROLES)

    def test_each_course_has_quiz(self):
        for c in self.env["slide.channel"].search([("name", "like", "Курс:")]):
            qs = self.env["slide.question"].search([("slide_id.channel_id", "=", c.id)])
            self.assertGreaterEqual(len(qs), 5, c.name)
            for q in qs:
                self.assertEqual(len(q.answer_ids.filtered("is_correct")), 1, q.question)
