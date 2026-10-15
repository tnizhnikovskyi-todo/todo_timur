from odoo import api, models


class F3dPushHandler(models.AbstractModel):
    _name = "f3d.push.handler"
    _description = "Телеметрія: обробник подій HTTP push"
    _f3d_push_routes = ()  # напр. ("lpr",)

    def _f3d_handle_push(self, route, event):
        """Хук CT-08. event = {"event_id", "route", "ts": datetime (UTC), "remote", "headers", "payload"}."""
        return None

    @api.model
    def _f3d_handler_models(self, route):
        """Імена моделей-обробників маршруту `route` (порядок за `_name`); абстрактна база не входить."""
        names = set()
        for cls in self.env.registry.descendants(["f3d.push.handler"], "_inherit"):
            name = getattr(cls, "_name", None)
            if name and name != "f3d.push.handler" and name in self.env and route in (cls._f3d_push_routes or ()):
                names.add(name)
        return sorted(names)
