"""norm_value: приведение значений домена и действия к сравнимому виду."""

import unittest

from odoo_graph_fixtures import og


class NormValueTest(unittest.TestCase):

    def test_strips_outer_whitespace(self):
        self.assertEqual(og.norm_value("  done  "), "done")

    def test_strips_single_quotes(self):
        self.assertEqual(og.norm_value("'done'"), "done")

    def test_strips_double_quotes(self):
        self.assertEqual(og.norm_value('"done"'), "done")

    def test_strips_whitespace_then_quotes(self):
        self.assertEqual(og.norm_value("  'Done'  "), "done")

    def test_lowercases(self):
        self.assertEqual(og.norm_value("APPROVED"), "approved")

    def test_booleans_become_words(self):
        # На эти строки опирается проверка недостижимых значений:
        # «false» считается достижимым значением по умолчанию.
        self.assertEqual(og.norm_value(False), "false")
        self.assertEqual(og.norm_value(True), "true")
        self.assertEqual(og.norm_value("True"), "true")

    def test_none_becomes_word(self):
        self.assertEqual(og.norm_value(None), "none")

    def test_numbers(self):
        self.assertEqual(og.norm_value(32), "32")
        self.assertEqual(og.norm_value("  5000 "), "5000")

    def test_empty_string(self):
        self.assertEqual(og.norm_value(""), "")
        self.assertEqual(og.norm_value("   "), "")

    def test_inner_quotes_survive(self):
        # Снимаются только внешние кавычки, разметка внутри значения остается.
        self.assertEqual(og.norm_value("""'a"b'"""), 'a"b')

    def test_idempotent(self):
        for raw in ("'Done'", "  x ", False, 12, None):
            once = og.norm_value(raw)
            self.assertEqual(og.norm_value(once), once)

    @unittest.expectedFailure
    def test_padding_inside_quotes_is_not_stripped(self):
        # НАЙДЕННЫЕ-БАГИ.md, находка 5: пробелы внутри кавычек остаются,
        # поэтому `' done '` из домена не сравнивается с `done` из действия.
        self.assertEqual(og.norm_value("' done '"), "done")


if __name__ == "__main__":
    unittest.main()
