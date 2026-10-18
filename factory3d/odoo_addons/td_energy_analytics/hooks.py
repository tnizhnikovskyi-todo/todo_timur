"""post_init_hook / uninstall_hook (W4_SPEC 5.4, 5.5). Усі кроки ідемпотентні; ті самі функції викликає міграція.

`post_init_hook`: `_load_areas` → `_assign_areas` → `_fill_alloc_product`. Драйвери, параметри й крони — XML;
базу й бюджет установка не створює.
"""

import csv
import io
import logging

from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "td_energy_analytics"
BATCH = 5000
FILL_SQL = """
UPDATE td_energy_alloc a SET product_id = p.product_id
  FROM mrp_production p
 WHERE a.production_id = p.id AND a.product_id IS NULL
   AND a.id IN (SELECT id FROM td_energy_alloc WHERE product_id IS NULL AND production_id IS NOT NULL
                 ORDER BY id LIMIT %s)
"""


def _rows(name):
    with file_open("%s/data/%s" % (MODULE, name), "rb") as f:
        text = f.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def _internal(env):
    return env(su=True, context=dict(env.context, tracking_disable=True, active_test=False))


def _load_areas(env):
    """5.2: 8 ділянок з `td_energy_area.csv`; наявні (за `code`) не змінюються — правки користувача зберігаються."""
    env = _internal(env)
    Area, Driver = env["td.energy.area"], env["td.energy.driver"]
    existing = {a.code for a in Area.search([])}
    created = 0
    for row in _rows("td_energy_area.csv"):
        if row["code"] in existing:
            continue
        driver = Driver.search([("code", "=", row["spec_driver"])], limit=1) if row.get("spec_driver") else Driver
        Area.create(
            {
                "code": row["code"], "name": row["name"], "sequence": int(row["sequence"]), "color": row["color"],
                "spec_driver_id": driver.id or False,
            }
        )  # fmt: skip
        created += 1
    return created


def _assign_areas(env):
    """5.2: `area_id` проставляється лише там, де порожній; невідомий вузол — пропуск із попередженням."""
    env = _internal(env)
    Node, Area = env["td.energy.node"], env["td.energy.area"]
    areas = {a.code: a.id for a in Area.search([])}
    nodes = {n.code: n for n in Node.search([("kind", "=", "consumer")])}
    done = 0
    for row in _rows("area_map.csv"):
        node, area_id = nodes.get(row["node_code"]), areas.get(row["area_code"])
        if node is None or not area_id:
            _logger.warning("td_energy_analytics: вузол %s або ділянка %s відсутні", row["node_code"], row["area_code"])
            continue
        if not node.area_id:
            node.write({"area_id": area_id})
            done += 1
    return done


def _fill_alloc_product(env):
    """5.4 п. 3: `product_id` у наявних рядків `td.energy.alloc` (SQL, пакети 5 000)."""
    env.flush_all()
    total = 0
    while True:
        env.cr.execute(FILL_SQL, (BATCH,))
        total += env.cr.rowcount
        if env.cr.rowcount < BATCH:
            break
    env["td.energy.alloc"].invalidate_model(["product_id"])
    return total


def _run(env):
    _load_areas(env)
    _assign_areas(env)
    _fill_alloc_product(env)


def post_init_hook(env):
    """5.4: `_load_areas` → `_assign_areas` → `_fill_alloc_product` (ідемпотентні)."""
    _run(env)


def uninstall_hook(env):
    """5.5: видаляє власні крони й параметри `td.energy_analytics.*`; електричні дані, `alloc` і вузли лишаються."""
    env = env(su=True)
    cron_ids = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id")
    env["ir.cron"].browse(cron_ids).exists().unlink()
    env.cr.execute("DELETE FROM ir_config_parameter WHERE key LIKE %s", ("td.energy\\_analytics.%",))
