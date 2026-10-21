"""REST цілей верстатів (контракт C-LP-01; SPEC §7.2 API-26): ``POST/GET /api/v1/machines/targets``.

Той самий застосунок і той самий токен SIM API, що й ``/sim/v1/*`` (``Authorization: Bearer <SIM_API_TOKEN>``;
403 при ``SIM_READONLY_API=1``, 423 при ``SIM_ENABLED=0``/``stop-all``): адреса — ``td.iot_sim.url``. Дублікат шляху
``/sim/v1/machines/targets`` — для клієнтів, що ходять префіксом керування. Реєструється з ``control_api.create_app``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from iot_sim.core.machine_targets import apply_targets, list_targets, to_epoch
from iot_sim.core.world import World

MAX_TARGETS = 500


class TargetItem(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    state: Literal["working", "idle", "down"]
    reason: str | None = Field(default=None, max_length=200)
    until: datetime


class TargetsBody(BaseModel):
    targets: list[TargetItem] = Field(max_length=MAX_TARGETS)


def register_machine_targets(
    app: FastAPI,
    get_world: Callable[[], World],
    read_auth: Callable[..., None],
    write_auth: Callable[..., None],
) -> None:
    @app.post("/api/v1/machines/targets", dependencies=[Depends(write_auth)])
    @app.post("/sim/v1/machines/targets", dependencies=[Depends(write_auth)])
    def post_targets(body: TargetsBody | list[TargetItem]) -> dict[str, Any]:
        items = body.targets if isinstance(body, TargetsBody) else body
        if len(items) > MAX_TARGETS:
            raise HTTPException(422, f"at most {MAX_TARGETS} targets per request")
        return apply_targets(get_world(), [(i.code, i.state, i.reason, to_epoch(i.until)) for i in items])

    @app.get("/api/v1/machines/targets", dependencies=[Depends(read_auth)])
    @app.get("/sim/v1/machines/targets", dependencies=[Depends(read_auth)])
    def get_targets() -> dict[str, Any]:
        items = list_targets(get_world())
        return {"count": len(items), "items": items}
