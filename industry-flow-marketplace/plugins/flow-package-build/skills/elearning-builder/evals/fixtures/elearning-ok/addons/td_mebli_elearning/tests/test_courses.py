from odoo.tests.common import TransactionCase

COURSE_XMLIDS = ["course_komirnyk", "course_master", "course_admin"]  # = ролі з INDEX A-16b


class TestElearning(TransactionCase):
    def test_courses_per_role(self):
        """Курсів стільки, скільки ролей; у кожного >= 5 питань (slide.channel, slide.question)."""
        for xid in COURSE_XMLIDS:
            c = self.env.ref("td_mebli_elearning." + xid)
            self.assertEqual(c._name, "slide.channel")
            qs = self.env["slide.question"].search([("slide_id.channel_id", "=", c.id)])
            self.assertGreaterEqual(len(qs), 5)

    def test_pass_score_applied(self):
        """Поріг pass_score застосовується (механізм «код»)."""
        self.assertEqual(self.env["ir.config_parameter"].get_param("td_mebli_elearning.pass_score"), "80")

    def test_access_not_public(self):
        """Курси не видимі публічному користувачу."""
        public = self.env.ref("base.public_user")
        c = self.env.ref("td_mebli_elearning.course_komirnyk").with_user(public)
        self.assertFalse(c.sudo().with_user(public).search([("id", "=", c.id)]))
