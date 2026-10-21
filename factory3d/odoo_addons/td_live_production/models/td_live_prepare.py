"""LP-07: підготовка демо-компанії. Крок налаштування модуля, ідемпотентний: повторний запуск нічого не міняє.

Назва компанії, валюта ₴, собівартість компонентів (лише де 0), зонний тариф з поточної доби, сценарії «Що якщо».
"""

import logging
from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

from ..tools import pricing, tariff

_logger = logging.getLogger(__name__)

COMPANY_NAME = "Меблеве підприємство"
CURRENCY = "base.UAH"
TARIFF_NAME = "Зонний тариф (демо-підприємство)"


class TdLiveEngine(models.AbstractModel):
    _inherit = "td.live.engine"

    @api.model
    def td_prepare_company(self):
        """Підготувати компанію. Повертає короткий звіт по кроках; бракуючі модулі-«м'які» залежності пропускає."""
        self = self.sudo()
        company = self.env.company
        uah = self.env.ref(CURRENCY)
        self._td_check_currency(company, uah)  # до будь-яких змін: якщо Odoo не дозволить, нічого не буде зроблено
        report = [
            self._td_prepare_name(company),
            self._td_prepare_currency(company, uah),
            self._td_prepare_costs(company),
            self._td_prepare_tariff(company),
            self._td_prepare_whatif(),
        ]
        return " ".join(r for r in report if r)

    @api.model
    def _td_check_currency(self, company, uah):
        """Валюту не можна змінити, коли є проводки: Odoo (account) забороняє. Пояснюємо заздалегідь."""
        if company.currency_id == uah:
            return
        blockers = []
        if "account.move.line" in self.env:
            count = self.env["account.move.line"].search_count([("company_id", "=", company.id)])
            if count:
                blockers.append(
                    _("у компанії є %s проводок (бухгалтерські записи в %s)", count, company.currency_id.name)
                )
        if blockers:
            raise UserError(
                _(
                    "Не можна змінити валюту компанії «%(company)s» з %(old)s на %(new)s: %(why)s. Odoo забороняє "
                    "змінювати валюту, коли є проводки. Підготуйте демо на базі без проводок або залиште валюту.",
                    company=company.name,
                    old=company.currency_id.name,
                    new=uah.name,
                    why="; ".join(blockers),
                )
            )

    @api.model
    def _td_prepare_name(self, company):
        if company.name == COMPANY_NAME:
            return ""
        old = company.name
        company.write({"name": COMPANY_NAME})
        return _("Назва компанії: «%(old)s» → «%(new)s».", old=old, new=COMPANY_NAME)

    @api.model
    def _td_prepare_currency(self, company, uah):
        """Валюта компанії — ₴. Замовлення продажу в іншій валюті переводяться на прайс у ₴ без перерахунку сум:
        демо-ціни завжди були гривнями (валюта USD у шаблоні — лише стандартна за замовчуванням)."""
        if company.currency_id == uah:
            return ""
        old = company.currency_id
        if not uah.active:
            uah.active = True
        try:
            with self.env.cr.savepoint():
                company.write({"currency_id": uah.id})
        except (UserError, ValidationError) as exc:
            raise UserError(
                _(
                    "Odoo не дозволив змінити валюту компанії «%(company)s» з %(old)s на %(new)s: %(err)s",
                    company=company.name,
                    old=old.name,
                    new=uah.name,
                    err=exc.args[0] if exc.args else exc,
                )
            ) from exc
        pricelist = self._td_uah_pricelist(company, uah)
        moved = self._td_orders_to_uah(company, uah, pricelist)
        return _(
            "Валюта компанії: %(old)s → %(new)s (замовлень переведено: %(n)s).", old=old.name, new=uah.name, n=moved
        )

    @api.model
    def _td_uah_pricelist(self, company, uah):
        Pricelist = self.env["product.pricelist"]
        found = Pricelist.search(
            [("currency_id", "=", uah.id), ("company_id", "in", [False, company.id])], order="id", limit=1
        )
        return found or Pricelist.create(
            {"name": _("Основний прайс (₴)"), "currency_id": uah.id, "company_id": company.id}
        )

    @api.model
    def _td_orders_to_uah(self, company, uah, pricelist):
        """Замовлення продажу компанії в іншій валюті → прайс у ₴ (суми рядків не змінюються)."""
        Order = self.env["sale.order"]
        orders = Order.search([("company_id", "=", company.id), ("currency_id", "!=", uah.id)])
        for order in orders:
            keep = {line.id: line.price_unit for line in order.order_line}
            # `sale.order.write` забороняє міняти прайс підтвердженого замовлення; демо-перехід на ₴ — виняток
            models.BaseModel.write(order.with_context(tracking_disable=True), {"pricelist_id": pricelist.id})
            for line in order.order_line:
                if line.id in keep and line.price_unit != keep[line.id]:
                    line.price_unit = keep[line.id]
        return len(orders)

    @api.model
    def _td_prepare_costs(self, company):
        """Собівартість компонентів у ₴ там, де вона 0 (вже задану не чіпаємо): оцінка за кодом, категорією."""
        env = self.env
        lines = env["mrp.bom.line"].search([("bom_id.company_id", "in", [False, company.id])])
        products = lines.product_id.with_company(company)
        n = 0
        for product in products:
            if product.standard_price:
                continue
            categ = product.categ_id.complete_name or ""
            product.standard_price = pricing.guess_unit_cost(product.default_code, categ)
            n += 1
        return _("Собівартість компонентів: заповнено %(n)s із %(all)s.", n=n, all=len(products)) if n else ""

    @api.model
    def _td_prepare_tariff(self, company):
        """Зонний тариф td_energy з УЧОРАШНЬОЇ доби (базовий період «Що якщо» закінчується вчора й має мати нічну зону);
        чинний плоский закривається за день до того. Тариф, створений раніше «з сьогодні», зсувається на вчора.
        Немає td_energy — пропуск."""
        if "td.energy.tariff" not in self.env:
            return ""
        Tariff = self.env["td.energy.tariff"]
        today = self._td_today()
        start = today - timedelta(days=1)
        named = Tariff.search([("name", "=", TARIFF_NAME), ("company_id", "=", company.id)], limit=1)
        if named:
            if named.date_from <= start:
                return ""
            prev = Tariff.search(
                [
                    ("company_id", "=", company.id),
                    ("id", "!=", named.id),
                    ("active", "=", True),
                    ("date_to", "=", named.date_from - timedelta(days=1)),
                    ("date_from", "<", start),
                ],
                limit=1,
            )
            if not prev:
                return ""
            prev.write({"date_to": start - timedelta(days=1)})
            named.write({"date_from": start})
            return _("Зонний тариф зсунуто на %s (щоб «Що якщо» бачило нічну зону).", start)
        current = Tariff.search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("date_from", "<=", start),
                "|",
                ("date_to", "=", False),
                ("date_to", ">=", start),
            ],
            order="date_from desc",
        )
        base = tariff.BASE_PRICE
        for old in current:
            zone = old.zone_ids[:1]
            if zone and len(old.zone_ids) == 1:
                base = zone.price or base
            if old.date_from < start:
                old.write({"date_to": start - timedelta(days=1)})
            else:
                old.write({"active": False})
        Tariff.create(
            {
                "name": TARIFF_NAME,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "date_from": start,
                "contract_kw": current[:1].contract_kw or 800,
                "zone_ids": [(0, 0, row) for row in tariff.zone_rows(base)],
            }
        )
        return _("Зонний тариф з %(day)s: ніч 0,5× / напівпік 1,0× / пік 1,5× від %(base)s ₴.", day=start, base=base)

    @api.model
    def _td_prepare_whatif(self):
        """Демо-сценарії «Що якщо» td_energy_analytics (у них своя ідемпотентність). Причини пропуску сценарію
        беруться з журналу самого сида: інакше «створено 1» не пояснює, чому не 2."""
        if "td.energy.whatif" not in self.env:
            return ""
        model = self.env["td.energy.whatif"]
        if not hasattr(model, "_td_seed_demo"):
            return ""
        logger = logging.getLogger("odoo.addons.td_energy_analytics.models.td_energy_whatif")
        handler = _Capture()
        level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            n = model._td_seed_demo()
        finally:
            logger.removeHandler(handler)
            logger.setLevel(level)
        skipped = [m.split("пропущено", 1)[-1].strip(": .") for m in handler.messages if "пропущено" in m]
        parts = []
        if n:
            parts.append(_("Сценарії «Що якщо»: створено %s.", n))
        if skipped:
            parts.append(_("Сценарії «Що якщо» пропущено: %s.", "; ".join(skipped)))
        return " ".join(parts)


class _Capture(logging.Handler):
    """Збирає повідомлення журналу на час одного виклику."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())
