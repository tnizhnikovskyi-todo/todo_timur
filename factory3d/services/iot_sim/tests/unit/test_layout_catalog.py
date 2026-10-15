"""catalog/odoo_demo.json (fire+lighting) збігається з dist/odoo_demo.json і підхоплюється load_layout."""
import json
from pathlib import Path

import pytest
from iot_sim.protocols.bacnet_server import load_layout

CAT = Path(__file__).resolve().parents[2] / "catalog" / "odoo_demo.json"
DIST = Path(__file__).resolve().parents[4] / "dist" / "odoo_demo.json"


def test_catalog_layout_loaded_by_default():
    assert load_layout()["fire"]["groups"]


@pytest.mark.skipif(not DIST.is_file(), reason="немає dist/odoo_demo.json")
def test_catalog_layout_in_sync_with_dist():
    full = json.loads(DIST.read_text(encoding="utf-8"))
    sub = json.loads(CAT.read_text(encoding="utf-8"))
    assert sub == {k: full[k] for k in ("fire", "lighting")}


def test_local_bip_loopback_and_prefix():
    """BACnet/IP: адреса з префіксом; без маршруту до peer — запасний (не падає)."""
    from iot_sim.__main__ import _local_bip, _mqtt_host

    assert _mqtt_host("mqtt://u:p@mosquitto:1883") == "mosquitto"
    a = _local_bip("127.0.0.1")
    ip, prefix = a.split("/")
    assert ip == "127.0.0.1" and prefix == "8"
    assert _local_bip("no-such-host.invalid").count("/") == 1


def test_helvar_version_from_env(monkeypatch):
    """ТК-17: SIM_HELVAR_VERSION=1 з env (рядок) приймається; без цього сервіс не стартував."""
    from iot_sim.config import Settings

    monkeypatch.setenv("SIM_HELVAR_VERSION", "1")
    assert Settings(_env_file=None).helvar_version == 1
    monkeypatch.setenv("SIM_HELVAR_VERSION", "2")
    assert Settings(_env_file=None).helvar_version == 2
