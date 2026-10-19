import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..services import checks, publish, snapshot, state as st
from ..services.registry import CHECKS, PLAN_BUILDERS, RENDERERS, SNAPSHOT_SECTIONS, SnapshotSection
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestRegistryHooks(F3DConstructorCase):
    """W0-B: споживачі реєстрів (checks.run_checks, publish.build_plan, snapshot.*) викликають записи слайсів;
    з порожніми реєстрами поведінка не змінюється."""

    def test_checks_registry_runs_registered_check(self):
        calls = []

        def probe(scene, config, eps):
            calls.append((config['params'], eps))
            return [
                {'check': 'inside', 'severity': config['mode'], 'layer_id': False, 'codes': ['W0B'], 'message': "probe"}
            ]

        def builtin_override(scene, config, eps):  # ключ вбудованої перевірки реєстром не перекривається
            raise AssertionError("вбудований ключ не повинен викликати реєстр")

        state = st.checks_state(self.site)
        configs = [{'check': 'inside', 'enabled': True, 'mode': 'warn', 'params': {'x': 1}}]
        before = checks.run_checks(state, configs)
        self.assertEqual(before, [])  # на площадці без місць справжня перевірка `inside` (S5) нічого не знаходить
        original = CHECKS.get('inside')  # S5 зареєстрував справжню перевірку: проба тимчасово її заміняє
        CHECKS.register('inside', probe, replace=True)
        CHECKS.register('fits', builtin_override)
        try:
            fits = {'check': 'fits', 'enabled': True, 'mode': 'block', 'params': {}}
            issues = checks.run_checks(state, configs + [fits])
            self.assertEqual([(i['check'], i['codes'], i['severity']) for i in issues], [('inside', ['W0B'], 'warn')])
            self.assertEqual(calls, [({'x': 1}, checks.DEFAULT_EPS_M)])
            calls.clear()
            checks.run_checks(state, [dict(configs[0], enabled=False)])
            checks.run_checks(state, [])
            self.assertEqual(calls, [])  # вимкнена або неналаштована — не викликається
        finally:
            CHECKS.register('inside', original, sequence=100, replace=True)
            CHECKS.unregister('fits')
        self.assertEqual(checks.run_checks(state, configs), before)

    def test_plan_builders_registry(self):
        base = publish.build_plan(self.site)

        def builder(site, env, lines, issues):
            lines.append(publish._line('create', 'stock.putaway.rule', 'W0B-RULE', "Правило", extra={'w0b': 1}))
            issues.append(publish._issue('code_conflict', 'warn', "probe", ['W0B-RULE']))
            return 3

        PLAN_BUILDERS.register('w0b_probe', builder)
        try:
            plan = publish.build_plan(self.site)
        finally:
            PLAN_BUILDERS.unregister('w0b_probe')
        self.assertEqual(len(plan['lines']), len(base['lines']) + 1)
        self.assertEqual(plan['lines'][-1]['code'], 'W0B-RULE')
        self.assertEqual(plan['unchanged'], base['unchanged'] + 3)
        self.assertEqual(plan['issues'][-1]['check'], 'code_conflict')
        self.assertEqual(publish.build_plan(self.site)['lines'], base['lines'])  # після зняття — як було

    def test_snapshot_sections_registry(self):
        store = {'value': {'n': 1}, 'applied': []}
        section = SnapshotSection(
            build=lambda site: store['value'], apply=lambda site, data: store['applied'].append(data)
        )
        empty = snapshot.build_snapshot(self.site)
        self.assertNotIn('sections', empty)
        SNAPSHOT_SECTIONS.register('w0b_probe', section)
        try:
            snap = snapshot.build_snapshot(self.site)
            self.assertEqual(snap['sections'], {'w0b_probe': {'n': 1}})
            self.assertEqual(snapshot.count_differences(snap, empty), 1)
            self.assertEqual(snapshot.count_differences(snap, snap), 0)
            snapshot.apply_snapshot(self.site, snap)
            snapshot.apply_snapshot(self.site, empty)  # у знімку розділу немає → apply(data=None)
            store['value'] = None
            self.assertNotIn('sections', snapshot.build_snapshot(self.site))  # порожній розділ не пишеться
        finally:
            SNAPSHOT_SECTIONS.unregister('w0b_probe')
        self.assertEqual(store['applied'], [{'n': 1}, None])
        self.assertEqual(snapshot.build_snapshot(self.site), empty)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestRegistryHooksApi(F3DConstructorHttpCase):
    """W0-B: API-05 і API-19 користуються реєстрами."""

    def test_validate_runs_registered_check(self):
        self.env['td.check.config'].create({'site_id': self.site.id, 'check_key': 'inside', 'mode': 'block'})

        def probe(scene, config, eps):
            return [{'check': 'inside', 'severity': 'block', 'layer_id': False, 'codes': ['A1'], 'message': "поза"}]

        self.authenticate(self.u_manager.login, PASSWORD)
        res = self.rpc('/f3d/constructor/validate', site_id=self.site.id)
        self.assertEqual(res['summary'], {'block': 0, 'warn': 0})
        original = CHECKS.get('inside')
        CHECKS.register('inside', probe, replace=True)
        try:
            res = self.rpc('/f3d/constructor/validate', site_id=self.site.id)
        finally:
            CHECKS.register('inside', original, sequence=100, replace=True)
        self.assertEqual(res['summary'], {'block': 1, 'warn': 0})
        self.assertEqual(res['issues'][0]['codes'], ['A1'])

    def test_render_dispatches_to_registered_renderer(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        self.assertEqual(self.rpc('/f3d/constructor/render/plan_pdf', scale=1)['code'], 'validation')  # рендерер S5

        def renderer(env, payload):
            if payload.get('scale') == 0:
                raise UserError("Масштаб має бути додатним.")
            return 'plan.pdf', 'application/pdf', b'%PDF-W0B ' + str(payload).encode()

        original = RENDERERS.get('plan_pdf')
        RENDERERS.register('plan_pdf', renderer, replace=True)
        try:
            res = self.rpc('/f3d/constructor/render/plan_pdf', scale=2)
            bad = self.rpc('/f3d/constructor/render/plan_pdf', scale=0)
            other = self.rpc('/f3d/constructor/render/spec_pdf')
        finally:
            RENDERERS.register('plan_pdf', original, sequence=30, replace=True)
        self.assertTrue(res['ok'], res)
        self.assertEqual((res['filename'], res['mimetype']), ('plan.pdf', 'application/pdf'))
        self.assertEqual(base64.b64decode(res['content']), b"%PDF-W0B {'scale': 2}")
        self.assertEqual((bad['ok'], bad['code']), (False, 'validation'))
        self.assertEqual(other['code'], 'validation')  # інші ключі — власні рендерери (spec_pdf без таблиць)
