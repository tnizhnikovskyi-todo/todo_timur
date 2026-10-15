"""Налаштування сервісу: усі змінні SIM_* (SPEC §8.2.1)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_TOKEN_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIM_", env_file=".env", extra="ignore")

    enabled: bool = True
    api_token: str = ""  # обов'язково, >= 32 симв. (validate_required)
    readonly_api: bool = False
    mode: Literal["scenario", "follow_odoo"] = "scenario"
    factor: float = 1.0
    seed: int = 20261012
    tz: str = "Europe/Kyiv"
    start_at: str = ""
    sun_model: Literal["astral", "parabola"] = "astral"
    tick_ms: int = 1000
    catalog_source: Literal["odoo", "local"] = "odoo"
    catalog_dir: str = "./catalog"
    state_dir: str = "./state"
    snapshot_s: int = 60
    restore_snapshot: bool = True
    level0_sync: bool = True
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_user: str = ""
    odoo_apikey: str = ""
    odoo_export_token: str = ""
    odoo_follow_s: int = 10
    odoo_follow_slow_s: int = 60
    odoo_stale_s: int = 120
    mqtt_url: str = "mqtt://user:pass@mosquitto:1883"
    mqtt_prefix: str = "f3d"
    lpr_push_url: str = "http://127.0.0.1:8090/sim/v1/lpr-sink"
    allow_outbound: str = "mosquitto,odoo19,collector,genset_relay,127.0.0.1"
    genset_relay_url: str = "http://genset_relay:8000"
    genset_relay_token: str = ""
    genset_amf_master: Literal["hgm", "ats"] = "hgm"
    genset_kw_max: float = 558.0
    helvar_version: Literal[1, 2] = 2
    biostar_user: str = "admin"
    biostar_pass: str = ""
    woodstore_apikey: str = ""
    jobs_apikey: str = ""
    opcua_cert_dir: str = "./certs"
    opcua_user: str = "collector"
    opcua_pass: str = ""
    yard_autogate: bool = True
    write_accept: bool = True  # SIM_WRITE_ACCEPT: приймати команди запису (Modbus DO/FC06, BACnet, SICS TA)
    log_level: str = "INFO"
    log_json: bool = True

    # порти §8.1.3 (SIM_PORT_*)
    port_opcua: int = 4840
    port_modbus: int = 502
    port_bacnet: int = 47808
    port_helvar_tcp: int = 50000
    port_helvar_udp: int = 50001
    port_biostar_https: int = 8443
    port_biostar_http: int = 8081
    port_woodstore: int = 8082
    port_jobs: int = 8083
    port_sics: int = 4001
    port_control: int = 8090

    @field_validator("helvar_version", mode="before")
    @classmethod
    def _helvar_int(cls, v: Any) -> Any:
        """SIM_HELVAR_VERSION приходить з env рядком «1»/«2» (Literal[1, 2] його б відхилив — рестарт падав)."""
        return int(v) if isinstance(v, str) and v.strip().isdigit() else v

    def allow_outbound_hosts(self) -> list[str]:
        return [h.strip() for h in self.allow_outbound.split(",") if h.strip()]

    def validate_required(self) -> list[str]:
        """Повертає список проблем (порожній — конфіг валідний)."""
        errors: list[str] = []
        if len(self.api_token) < MIN_TOKEN_LEN:
            errors.append(f"SIM_API_TOKEN обов'язковий, >= {MIN_TOKEN_LEN} символів")
        for name in ("biostar_pass", "woodstore_apikey", "jobs_apikey", "opcua_pass"):
            if not getattr(self, name):
                errors.append(f"SIM_{name.upper()} обов'язковий")
        return errors
