import re
from pathlib import Path

from odoo.tests import tagged

from .common import PASSWORD, F3DConstructorHttpCase

MODULE = Path(__file__).resolve().parents[1]
CORE_TOPICS = MODULE.parents[1] / 'core' / 'constructor' / 'help_topics.js'
TOUR_DEFS = MODULE.parents[1] / 'core' / 'constructor' / 'tour_defs.js'


def js_topics():
    """[(id, назва UK, назва EN)] з core/constructor/help_topics.js (рядок `["id", ["UK", "EN"], …]`)."""
    text = CORE_TOPICS.read_text(encoding='utf-8')
    return re.findall(r'^\s*\["(\w+)", \["([^"]+)", "([^"]+)"\]', text, re.M)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestHelp(F3DConstructorHttpCase):
    """F19-01: сторінка «Інструкція» (QWeb) має ті самі 36 тем, що й редактор, українською й англійською."""

    def test_topics_in_sync(self):
        topics = js_topics()
        self.assertEqual(len(topics), 36)
        self.assertEqual(len({t[0] for t in topics}), 36)
        xml = (MODULE / 'views' / 'td_help.xml').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'<section id="topic-(\w+)"', xml), [t[0] for t in topics])
        for _id, uk, en in topics:
            self.assertIn('<t t-if="en">%s</t><t t-else="">%s</t>' % (en, uk), xml.replace('&amp;', '&'), uk)

    def test_tour_catalogue(self):
        ids = re.findall(r'^\s*id: "(\w+)",$', TOUR_DEFS.read_text(encoding='utf-8'), re.M)
        self.assertEqual(
            ids,
            [
                'welcome',
                'basic',
                'rack',
                'import',
                'scratch',
                'address',
                'putaway',
                'apply',
                'find',
                'labels',
                'docs',
                'team',
            ],
        )

    def test_help_route_renders_both_languages(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        uk = self.url_open('/f3d/constructor/help')
        self.assertEqual(uk.status_code, 200)
        self.assertEqual(len(re.findall(r'<section id="topic-', uk.text)), 36)
        self.assertIn('Блокування зон', uk.text)
        self.assertNotIn('Zone locks', uk.text)
        en = self.url_open('/f3d/constructor/help?lang=en')
        self.assertIn('Zone locks', en.text)
        self.assertNotIn('Блокування зон</h2>', en.text)
        menu = self.env.ref('td_constructor.menu_td_constructor_help')
        self.assertEqual(menu.action.url, '/f3d/constructor/help')

    def test_help_requires_login(self):
        res = self.url_open('/f3d/constructor/help', allow_redirects=False)
        self.assertIn(res.status_code, (303, 401, 403))
