"""Маркер `stand` для ТК-H1…ТК-H3 (pytest проти стенда)."""


def pytest_configure(config):
    config.addinivalue_line("markers", "stand: стендові тести (Odoo + браузер)")
