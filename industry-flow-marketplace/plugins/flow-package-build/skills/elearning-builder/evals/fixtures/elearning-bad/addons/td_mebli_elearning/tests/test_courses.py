from odoo.tests.common import TransactionCase


class TestElearning(TransactionCase):
    def test_courses_per_role(self):
        """Курсів стільки, скільки ролей; у кожного >= 5 питань (slide.channel, slide.question)."""
        courses = self.env["slide.channel"].search([("name", "like", "Курс:")])
        self.assertEqual(len(courses), 3)
        for c in courses:
            qs = self.env["slide.question"].search([("slide_id.channel_id", "=", c.id)])
            self.assertGreaterEqual(len(qs), 5)
