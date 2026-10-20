{
    "name": "Sales Order Live Cost",
    "summary": "Live cost and margin of a sales order from real production data (work orders, energy, components)",
    "description": """
Sales Order Live Cost
=====================

Bridge between the sales order and the manufacturing data of Factory 3D. It is installed automatically with the sales manufacturing bridge and Factory 3D.

Key features
------------

* Smart button on the sales order: actual cost and margin
* Breakdown by cost item (machines, energy, materials, waste) and by manufacturing order, plan versus actual with a colored deviation
* Margin plan and actual columns in the sales order list
* Everything is recalculated on open, nothing is stored

Requirements and notes
----------------------

* Machine time comes from the Machine Connect state log when installed, otherwise from the work order time log.
* Energy comes from the Energy allocation to manufacturing orders when installed.
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["sale_mrp", "td_factory3d"],
    "data": [
        "security/ir.model.access.csv",
        "views/td_sale_cost_views.xml",
        "views/sale_order_views.xml",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
}
