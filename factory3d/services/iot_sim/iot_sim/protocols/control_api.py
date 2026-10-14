"""REST керування /sim/v1 (SPEC §7.2). W0: лише /health (§8.16)."""
from __future__ import annotations

import time

from fastapi import FastAPI

from iot_sim import __version__
from iot_sim.config import Settings

_STARTED = time.monotonic()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="iot_sim control API", version=__version__)

    @app.get("/sim/v1/health")
    def health() -> dict:
        locked = settings is not None and not settings.enabled
        return {
            "status": "locked" if locked else "ok",
            "version": __version__,
            "uptime_s": round(time.monotonic() - _STARTED, 1),
            "servers": {},
        }

    return app
