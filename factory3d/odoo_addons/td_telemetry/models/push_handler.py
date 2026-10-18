from odoo import api, models


class F3dPushHandler(models.AbstractModel):
    _name = "td.push.handler"
    _description = "Телеметрія: обробник подій HTTP push"
    _f3d_push_routes = ()  # напр. ("lpr",)

    def _f3d_handle_push(self, route, event):
        """Хук CT-08. event = {"event_id", "route", "ts": datetime (UTC), "remote", "headers", "payload"}."""
        return None

    @api.model
    def _f3d_handler_models(self, route):
        """Імена моделей-обробників маршруту `route` (порядок за `_name`); абстрактна база не входить."""
        names = set()
        for name in self.env.registry.descendants(["td.push.handler"], "_inherit"):
            if name == "td.push.handler" or name not in self.env:
                continue
            cls = self.env.registry[name]
            if route in (cls._f3d_push_routes or ()):
                names.add(name)
        return sorted(names)
