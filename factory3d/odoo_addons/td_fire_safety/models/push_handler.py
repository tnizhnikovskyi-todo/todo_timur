import re
from datetime import datetime, timedelta, timezone

from odoo import api, models

from ..tools import sanitize, states

ADDRESS_RE = re.compile(r"\b[0-4]\.[A-Z0-9-]{2,8}\.[0-9]{2}\b")
OBJECT_ALIASES = {
    "life-safety-zone": "LSZ", "life-safety-point": "LSP", "binary-input": "BI", "binary-value": "BV",
    "analog-value": "AV", "multi-state-value": "MSV", "positive-integer-value": "PIV"}
REQUIRED = (("device", int), ("object", str), ("instance", int), ("event_type", str), ("ts", str))
BACK_TO_NORMAL = {"alarm": "reset", "prealarm": "reset", "fault": "fault_ok", "disabled": "enabled",
                  "test": "test_end"}


class F3dPushHandlerFire(models.AbstractModel):
    _name = "td.push.handler.fire"
    _inherit = "td.push.handler"
    _description = "Пожежна безпека: обробник повідомлень BACnet"
    _td_push_routes = ("bacnet_event",)

    @api.model
    def _td_parse(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("bacnet_event: payload")
        for name, typ in REQUIRED:
            value = payload.get(name)
            if value is None or isinstance(value, bool) or not isinstance(value, typ):
                raise ValueError("bacnet_event: %s" % name)
        if payload["instance"] < 0:
            raise ValueError("bacnet_event: instance")
        obj = payload["object"].strip()
        if len(obj) > 40 or not obj:
            raise ValueError("bacnet_event: object")
        if len(payload["event_type"]) > 64:
            raise ValueError("bacnet_event: event_type")
        try:
            ts = datetime.fromisoformat(payload["ts"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                raise ValueError("naive")
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            raise ValueError("bacnet_event: ts") from None
        obj = OBJECT_ALIASES.get(obj.lower(), obj.upper())
        text = sanitize.clean_text(payload.get("message_text") or "", 500)
        return {
            "device": payload["device"], "object": obj, "instance": payload["instance"], "ts": ts,
            "from": str(payload.get("from_state") or "")[:32], "to": str(payload.get("to_state") or "")[:32],
            "text": text}

    def _td_handle_push(self, route, event):
        if route != "bacnet_event":
            return super()._td_handle_push(route, event)
        data = self._td_parse((event or {}).get("payload"))
        env = self.env
        Event = env["td.fire.event"].sudo()
        panel = env["td.fire.panel"].sudo().search([], limit=1)
        device_no = ((panel.source_id.params or {}).get("device") if panel.source_id else None)
        if device_no is not None and device_no != data["device"]:
            return None  # X-44: чужий device instance, DEBUG
        code = panel.code or "FACP-1"
        obj, inst = data["object"], data["instance"]
        links = {"panel_id": panel.id}
        if obj == "LSZ" and inst:
            zone = env["td.fire.zone"].sudo().search([("lsz_instance", "=", inst)], limit=1)
            if zone:
                code = zone.code
                links["zone_id"] = zone.id
        elif obj == "LSP":
            device = env["td.fire.device"].sudo().search([("lsp_instance", "=", inst)], limit=1)
            if device:
                code = device.address
                links.update(device_id=device.id, zone_id=device.zone_id.id)
        to_state = states.normalize(data["to"])
        state = states.ZONE_MAP.get(to_state)
        etype = self._td_etype(state, to_state, states.normalize(data["from"]))
        ts = data["ts"]
        message = data["text"]
        found_dev = env["td.fire.device"]
        match = ADDRESS_RE.search(message) if message else None
        if match:
            found_dev = env["td.fire.device"].sudo().search([("address", "=", match.group(0))], limit=1)
        if etype:
            existing = Event.search([
                ("etype", "=", etype), ("object_code", "=", code),
                ("ts", ">=", ts - timedelta(seconds=5)), ("ts", "<=", ts + timedelta(seconds=5))],
                order="ts desc, id desc", limit=1)
            if existing:
                vals = {}
                if message:
                    vals["message_text"] = message
                if found_dev and not existing.device_id:
                    vals["device_id"] = found_dev.id
                if vals:
                    existing.write(vals)
                return existing.id
        text = "BACnet: %s" % (message or "%s:%s %s → %s" % (obj, inst, data["from"], data["to"]))
        if found_dev:
            links["device_id"] = found_dev.id
        ev = Event._log("bacnet", code, ts, text, source="bacnet", message_text=message or False,
                        raw_from=data["from"] or False, raw_to=data["to"] or False, **links)
        return ev.id

    @api.model
    def _td_etype(self, state, to_state, from_state):
        """Тип переходу за R-14 п. 1/5; `None` — переходу в таблиці немає (нова подія `bacnet`)."""
        if state in ("test", "alarm", "prealarm", "fault", "disabled"):
            return state
        if state == "normal":
            return BACK_TO_NORMAL.get(states.ZONE_MAP.get(from_state))
        return None
