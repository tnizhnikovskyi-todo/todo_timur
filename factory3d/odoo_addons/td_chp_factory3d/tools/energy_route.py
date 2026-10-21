"""RB-01…RB-04: чиста частина маршрутизації команд КГУ через td_energy_control (D-15) — мапінг видів і тексти.

Усі 9 видів td_chp ідуть у `td.energy.action` з виконавцем `chp` (`data/td_energy_command_kind_data.xml`):
`start`/`stop` — наявні `chp_start`/`chp_stop` td_energy_control (клас B), яким міст замінює виконавця `intent`
на `chp`, решта 7 — види моста. Запис — `td.command` (`origin='energy'`) у `chp/ctl/*` (Modbus u72), верифікація
за `chp/ctl/ack` / значенням цілі (R-09). Інтент збирача енергетики (`energy_control/intent`) для КГУ не
використовується: його `chp_cmd` — вікно керування ГРЩ (`energy_control/chp/cmd`, u73:230), а не карта u72.
"""

from odoo.addons.td_chp.tools import command_flow as flow

EXECUTOR = "chp"
KIND_TO_ENERGY = {
    "start": "chp_start",
    "stop": "chp_stop",
    "estop": "chp_estop",
    "reset": "chp_reset",
    "set_mode": "chp_set_mode",
    "set_setpoint": "chp_set_setpoint",
    "set_cos": "chp_set_cos",
    "set_heat_dir": "chp_set_heat_dir",
    "set_bypass": "chp_set_bypass",
}
ENERGY_TO_KIND = {v: k for k, v in KIND_TO_ENERGY.items()}
ENERGY_KINDS = tuple(KIND_TO_ENERGY.values())
BRIDGE_KINDS = ENERGY_KINDS  # усі 9 видів — виконавець `chp`
AUTO_LIKE = "auto\\_%chp%"  # `kind_code ilike` для дій автоматики КГУ (RB-03)
ACK_KINDS = ("start", "stop", "estop", "reset")  # команди `ctl/cmd` — за `chp/ctl/ack`; `set_*` — за значенням цілі


def energy_code(kind):
    """Вид td_chp → код `td.energy.command.kind`; невідомий → `None`."""
    return KIND_TO_ENERGY.get(kind)


def chp_kind(code):
    """Код `td.energy.command.kind` → вид td_chp; не КГУ → `None`."""
    return ENERGY_TO_KIND.get(code)


def target_signal(kind):
    """Сигнал цілі виду без префікса `chp/` (`ctl/cmd`, `ctl/mode`, …)."""
    return flow.KINDS[kind]["signal"]


def expectation(kind, params, scale):
    """Що має показати контролер після виконання (R-09): `ack` або значення цілі з допуском ½ кроку регістра."""
    if kind in ACK_KINDS:
        return {"signal": "chp/ctl/ack", "kind": "ack"}
    value = flow.target_value(kind, params)
    return {"signal": "chp/" + target_signal(kind), "kind": "value", "value": value, "tol": 0.5 * abs(scale or 1.0)}


def text_values(kind, params):
    """Підписи для шаблонів видів моста (`{mode_label}`, `{dir_label}`, `{bypass_label}`, `{sp_text}`, `{cos_text}`)."""
    params = params or {}
    out = {}
    if kind == "set_mode":
        out["mode_label"] = flow.MODE_LABELS.get(params.get("mode"), "—")
    elif kind == "set_heat_dir":
        out["dir_label"] = flow.HEAT_LABELS.get(params.get("dir"), "—")
    elif kind == "set_bypass":
        out["bypass_label"] = flow.BYPASS_LABELS.get(params.get("mode"), "—")
    elif kind == "set_setpoint" and params.get("sp_pct") is not None:
        out["sp_text"] = flow.fmt_num(params["sp_pct"], 1)
    elif kind == "set_cos" and params.get("cos") is not None:
        out["cos_text"] = flow.fmt_num(params["cos"], 2)
    return out
