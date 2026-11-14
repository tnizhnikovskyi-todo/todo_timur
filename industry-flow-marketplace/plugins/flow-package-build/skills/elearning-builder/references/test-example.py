# ПРИКЛАД-ЧЕРНЕТКА тесту модуля td_<галузь>_elearning (звірити імена моделей/полів з вихідниками 19.0).
from odoo.tests.common import TransactionCase

# xml-id курсів модуля: по одному на роль із таблиці «Ролі» INDEX A-16b (admin включно). Курси шукаємо за xml-id, не за назвою.
COURSE_XMLIDS = ["course_komirnyk", "course_master", "course_admin"]
MODULE = "td_<галузь>_elearning"


class TestElearning(TransactionCase):
    def test_courses_per_role(self):
        data = self.env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "slide.channel")])
        self.assertEqual(len(data), len(COURSE_XMLIDS))  # курсів = ролей

    def test_each_course_has_quiz(self):
        for xid in COURSE_XMLIDS:
            c = self.env.ref(f"{MODULE}.{xid}")
            qs = self.env["slide.question"].search([("slide_id.channel_id", "=", c.id)])
            self.assertGreaterEqual(len(qs), 5, xid)
            for q in qs:
                correct = len(q.answer_ids.filtered("is_correct"))
                # multi: true -> >=1 правильна; інакше рівно одна
                self.assertEqual(correct, 1, q.question)

    def test_pass_score_applied(self):
        """Механізм «код»: перевірка застосування порога (прибрати, якщо поріг штатний/survey; тоді тест штатного механізму)."""
        raise NotImplementedError("порівняти відсоток із td_<галузь>_elearning.pass_score за обраним механізмом")

    def test_access_not_public(self):
        """EL-access: курс не видимий публічному користувачу (механізм — за вихідниками 19.0)."""
        public = self.env.ref("base.public_user")
        for xid in COURSE_XMLIDS:
            c = self.env.ref(f"{MODULE}.{xid}")
            self.assertFalse(self.env["slide.channel"].with_user(public).search([("id", "=", c.id)]), xid)
