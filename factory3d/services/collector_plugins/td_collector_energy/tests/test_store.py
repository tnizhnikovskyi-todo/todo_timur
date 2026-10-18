"""AC-267: Store — атомарний запис (tmp + rename), відкидання > 7 діб, 500 інтентів / 24 год, пошкоджений файл."""

import json
import os
from datetime import timedelta

from helpers import T0

from td_collector_energy import store as store_mod
from td_collector_energy.store import Store


def test_roundtrip_and_atomic_file(tmp_path):
    st = Store(tmp_path)
    st.load(T0)
    st.data["engine"]["shared"] = {"bess_by": "peak"}
    st.cache_config({"config_version": 3}, T0)
    assert st.save(T0)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["td_energy_ctl.json"]  # tmp не лишається
    raw = json.loads((tmp_path / "td_energy_ctl.json").read_text("utf-8"))
    assert raw["v"] == 1 and raw["engine"]["shared"] == {"bess_by": "peak"}
    st2 = Store(tmp_path)
    st2.load(T0 + timedelta(hours=1))
    assert st2.data["engine"]["shared"]["bess_by"] == "peak" and st2.problem is None
    assert st2.cached_config(T0 + timedelta(hours=1)) == {"config_version": 3}


def test_failed_replace_keeps_previous_file_intact(tmp_path, monkeypatch):
    st = Store(tmp_path)
    st.data["engine"]["shared"] = {"v": 1}
    st.save(T0)
    before = (tmp_path / "td_energy_ctl.json").read_text("utf-8")
    st.data["engine"]["shared"] = {"v": 2}

    def boom(src, dst):
        raise OSError("диск повний")

    monkeypatch.setattr(os, "replace", boom)
    assert st.save(T0 + timedelta(seconds=10)) is False  # помилка запису не валить плагін
    assert (tmp_path / "td_energy_ctl.json").read_text("utf-8") == before


def test_state_older_than_7_days_is_discarded(tmp_path):
    st = Store(tmp_path)
    st.data["engine"]["shared"] = {"x": 1}
    st.save(T0)
    old = Store(tmp_path)
    old.load(T0 + timedelta(days=7, seconds=1))
    assert old.data["engine"] == {} and old.problem and "7 діб" in old.problem
    fresh = Store(tmp_path)
    fresh.load(T0 + timedelta(days=6, hours=23))
    assert fresh.data["engine"]["shared"] == {"x": 1}


def test_corrupted_file_starts_empty_with_problem(tmp_path):
    (tmp_path / "td_energy_ctl.json").write_text("{не json", encoding="utf-8")
    st = Store(tmp_path)
    st.load(T0)
    assert st.data["engine"] == {} and st.data["intents"] == {} and st.problem.startswith("стан пошкоджено")
    (tmp_path / "td_energy_ctl.json").write_text(
        json.dumps({"v": 99, "saved_at": "2026-10-14T06:00:00Z", "engine": {}})
    )
    st2 = Store(tmp_path)
    st2.load(T0)
    assert st2.problem and st2.data["intents"] == {}


def test_intents_kept_24h_or_500(tmp_path):
    st = Store(tmp_path)
    now = T0.timestamp()
    for i in range(600):
        st.intents[f"k{i}"] = {"state": "done", "ts": now - i}  # k0 — найновіший
    st.intents["old"] = {"state": "done", "ts": now - 25 * 3600}
    st.prune(T0)
    assert len(st.intents) == store_mod.limits.INTENT_KEEP_N == 500
    assert "old" not in st.intents and "k0" in st.intents and "k499" in st.intents and "k500" not in st.intents


def test_config_cache_expires_after_7_days(tmp_path):
    st = Store(tmp_path)
    assert st.cached_config(T0) is None
    st.cache_config({"config_version": 1}, T0)
    assert st.cached_config(T0 + timedelta(days=6)) == {"config_version": 1}
    assert st.cached_config(T0 + timedelta(days=8)) is None


def test_save_throttle_and_no_state_dir():
    st = Store(None)
    assert st.save(T0) is False  # без state_dir — у пам'яті
    st.load(T0)


def test_save_min_interval(tmp_path):
    st = Store(tmp_path)
    assert st.save(T0, min_interval_s=5) is True
    assert st.save(T0 + timedelta(seconds=2), min_interval_s=5) is False
    assert st.save(T0 + timedelta(seconds=6), min_interval_s=5) is True and st.saves == 2
