"""ТК-H1…ТК-H3 — pytest проти стенда (W4-C, W4_SPEC H.13): мобільний екран «Чергування» у браузері (Playwright,
viewport 390 × 844) поверх Odoo зі встановленими `td_energy` і `td_energy_mobile`.

Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER (за замовчуванням admin), F3D_ODOO_PASSWORD; для ТК-H2 — другий
енергетик: F3D_ODOO_USER_B / F3D_ODOO_PASSWORD_B (немає — тест створює користувача `wh_tk_b` і видаляє наприкінці);
F3D_STAND_SHOTS — каталог для скриншотів (необов'язково); PLAYWRIGHT_BROWSERS_PATH — Chromium Playwright.
Без F3D_ODOO_URL усі тести пропускаються. Запуск: `pytest -m stand tests/stand/test_wh_tk.py`.
"""

from __future__ import annotations

import os
import time
import xmlrpc.client
from datetime import datetime, timedelta

import pytest

pytestmark = [
    pytest.mark.stand,
    pytest.mark.skipif(not os.environ.get("F3D_ODOO_URL"), reason="F3D_ODOO_URL не задано: стенд не піднято"),
]

VIEWPORT = {"width": 390, "height": 844}
ACTION = "/odoo/action-td_energy.action_td_energy_mobile"
OPEN_STATES = ["open", "in_progress"]


class Rpc:
    """Тонка обгортка над `xmlrpc/2` (як `td_energy/tests/stand/helpers.py`)."""

    def __init__(self, url, db, user, password):
        self.url, self.db, self.user, self.password = url.rstrip("/"), db, user, password
        self.uid = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common").authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError(f"Odoo: автентифікація {user} не вдалась")
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def k(self, model, method, *args, **kw):
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)


def _env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        pytest.skip(f"не задано {name}")
    return value


@pytest.fixture(scope="module")
def odoo():
    rpc = Rpc(_env("F3D_ODOO_URL"), _env("F3D_ODOO_DB"), _env("F3D_ODOO_USER", "admin"), _env("F3D_ODOO_PASSWORD"))
    assert rpc.k("ir.config_parameter", "get_param", "td.base.environment") == "test", "стенд має бути «test»"
    key = rpc.k("ir.config_parameter", "search", [("key", "=", "td.energy.read_enabled")])
    rpc.k("ir.config_parameter", "write", key, {"value": "True"})
    return rpc


@pytest.fixture(scope="module")
def template_id(odoo):
    ids = odoo.k("td.energy.round.template", "search", [("code", "=", "TP-GRSH")])
    assert ids, "шаблон TP-GRSH не встановлено"
    return ids[0]


@pytest.fixture(autouse=True)
def clean_rounds(odoo):
    """Кожен ТК стартує без обходів (журнал стенда — тестовий)."""
    odoo.k("td.energy.round", "unlink", odoo.k("td.energy.round", "search", []))
    yield


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        chromium = pw.chromium.launch()
        yield chromium
        chromium.close()


def _login(browser, user, password):
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()
    page.goto(_env("F3D_ODOO_URL").rstrip("/") + "/web/login?db=" + _env("F3D_ODOO_DB"))
    page.fill("input[name=login]", user)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".o_navbar, .o_web_client", timeout=30000)
    return context, page


def _open_mobile(page):
    page.goto(_env("F3D_ODOO_URL").rstrip("/") + ACTION)
    page.wait_for_selector(".o_td_en_mobile .o_td_en_m_tab", timeout=30000)


def _shot(page, name):
    shots = os.environ.get("F3D_STAND_SHOTS")
    if shots:
        os.makedirs(shots, exist_ok=True)
        page.screenshot(path=os.path.join(shots, name + ".png"))


def _no_hscroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert page.evaluate("document.querySelector('.o_td_en_mobile').scrollWidth <= 390")


def _min_height(page, selector):
    """Висота кожної видимої кнопки (`getBoundingClientRect`) ≥ 48 px."""
    heights = page.evaluate(
        "(s) => Array.from(document.querySelectorAll(s)).filter((e) => e.offsetParent !== null)"
        ".map((e) => Math.round(e.getBoundingClientRect().height))",
        selector,
    )
    assert heights and min(heights) >= 48, (selector, heights)


def test_tk_h1_full_screen(odoo, template_id, browser):
    """ТК-H1 (AC-H19): Стан → Тривоги («Беру в роботу») → Схема → Обхід (6 пунктів, «Завершити») → журнал і події."""
    round_id = odoo.k("td.energy.round", "action_start", template_id)
    context, page = _login(browser, _env("F3D_ODOO_USER", "admin"), _env("F3D_ODOO_PASSWORD"))
    try:
        _open_mobile(page)
        assert page.locator(".o_td_en_m_tab").count() == 4
        _no_hscroll(page)
        _shot(page, "tk_h1_state")
        _min_height(page, ".o_td_en_m_tab")
        page.click(".o_td_en_m_tab_alarms")
        page.wait_for_selector(".o_td_en_m_active_count")
        _shot(page, "tk_h1_alarms")
        label = page.inner_text(".o_td_en_m_tab_alarms")
        take = page.locator(".o_td_en_m_take")
        if take.count():  # на стенді є активна тривога: «Беру в роботу» змінює картку («У роботі · ви»)
            take.first.click()
            page.wait_for_selector(".o_td_en_m_tag--work", timeout=15000)
            assert page.inner_text(".o_td_en_m_tab_alarms") != "" and label
        _no_hscroll(page)
        page.click(".o_td_en_m_tab_scheme")
        page.wait_for_selector(".o_td_en_m_node")
        _shot(page, "tk_h1_scheme")
        page.click(".o_td_en_m_tab_round")
        page.wait_for_selector(".o_td_wh_item")
        assert page.locator(".o_td_wh_item").count() == 6
        _no_hscroll(page)
        _min_height(page, ".o_td_wh_finish, .o_td_wh_where3d")
        for _ in range(6):
            page.locator(".o_td_wh_check:not(:checked)").first.click()
        page.wait_for_function("document.querySelector('.o_td_wh_count').innerText.trim() === '6 / 6'")
        _shot(page, "tk_h1_round")
        page.click(".o_td_wh_finish")
        page.wait_for_selector("text=Обхід завершено й записано в журнал о", timeout=15000)
        _no_hscroll(page)
    finally:
        context.close()
    rnd = odoo.k("td.energy.round", "read", [round_id], ["state", "done_count", "deviation_count", "finished_at"])[0]
    assert (rnd["state"], rnd["done_count"]) == ("done", 6)
    events = odoo.k(
        "td.energy.event", "search_count", [("kind", "=", "round"), ("code", "like", f"ROUND-{round_id}-%")]
    )
    assert events == rnd["deviation_count"]  # подія на кожне відхилення (їх може не бути)


def test_tk_h2_two_sessions(odoo, template_id, browser):
    """ТК-H2 (AC-H20): A відмічає пункт; B ≤ 10 с бачить «Обхід виконує A» (читання); після завершення — «Останні»."""
    login_b, pass_b = os.environ.get("F3D_ODOO_USER_B"), os.environ.get("F3D_ODOO_PASSWORD_B")
    created = None
    if not login_b:
        login_b, pass_b = "wh_tk_b", "wh_tk_b_pass"
        groups = odoo.k(
            "res.groups",
            "search",
            [("id", "=", odoo.k("ir.model.data", "check_object_reference", "td_energy", "group_td_energy_manager")[1])],
        )
        created = odoo.k(
            "res.users",
            "create",
            {"name": "ТК-H2 B", "login": login_b, "password": pass_b, "group_ids": [(6, 0, groups)]},
        )
    odoo.k("td.energy.round", "action_start", template_id)
    ctx_a, page_a = _login(browser, _env("F3D_ODOO_USER", "admin"), _env("F3D_ODOO_PASSWORD"))
    ctx_b, page_b = _login(browser, login_b, pass_b)
    try:
        for page in (page_a, page_b):
            _open_mobile(page)
            page.click(".o_td_en_m_tab_round")
            page.wait_for_selector(".o_td_wh_item")
        page_a.locator(".o_td_wh_check").first.click()
        page_a.wait_for_function("document.querySelector('.o_td_wh_count').innerText.trim() === '1 / 6'")
        page_b.wait_for_selector(".o_td_wh_banner", timeout=10000)
        assert "Обхід виконує" in page_b.inner_text(".o_td_wh_banner")
        assert page_b.locator(".o_td_wh_check:not(:disabled)").count() == 0  # B не може відмітити
        _shot(page_b, "tk_h2_session_b")
        for _ in range(5):
            page_a.locator(".o_td_wh_check:not(:checked)").first.click()
        page_a.wait_for_function("document.querySelector('.o_td_wh_count').innerText.trim() === '6 / 6'")
        page_a.click(".o_td_wh_finish")
        page_a.wait_for_selector("text=Обхід завершено й записано в журнал о", timeout=15000)
        page_b.wait_for_selector(".o_td_wh_hist_row", timeout=10000)  # у «Останніх» B бачить завершений обхід
    finally:
        ctx_a.close()
        ctx_b.close()
        if created:
            odoo.k("res.users", "write", [created], {"active": False})


def test_tk_h3_missed_slot(odoo, template_id, browser):
    """ТК-H3: слот минув, обхід не завершено → `cron_close`: `missed`, подія в «Подіях», «Не виконано» в «Останніх»."""
    now = datetime.utcnow()
    fmt = "%Y-%m-%d %H:%M:%S"
    round_id = odoo.k(
        "td.energy.round", "create",
        {"template_id": template_id, "slot_name": "ТК-H3", "date": (now - timedelta(hours=3)).strftime("%Y-%m-%d"),
         "starts_at": (now - timedelta(hours=4)).strftime(fmt), "due_at": (now - timedelta(hours=1)).strftime(fmt),
         "state": "in_progress"},
    )  # fmt: skip
    cron = odoo.k("ir.model.data", "check_object_reference", "td_energy_mobile", "cron_td_energy_round_close")[1]
    odoo.k("ir.cron", "method_direct_trigger", [cron])
    time.sleep(1)
    rnd = odoo.k("td.energy.round", "read", [round_id], ["state", "finished_at", "due_at"])[0]
    assert rnd["state"] == "missed" and rnd["finished_at"] == rnd["due_at"]
    assert odoo.k("td.energy.event", "search_count", [("kind", "=", "round"), ("code", "=", f"ROUND-{round_id}")]) == 1
    context, page = _login(browser, _env("F3D_ODOO_USER", "admin"), _env("F3D_ODOO_PASSWORD"))
    try:
        _open_mobile(page)
        page.click(".o_td_en_m_tab_round")
        page.wait_for_selector(".o_td_wh_hist_row")
        assert "Не виконано" in page.inner_text(".o_td_wh_history")
        _shot(page, "tk_h3_missed")
    finally:
        context.close()
