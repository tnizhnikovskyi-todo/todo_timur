{
    "name": "Factory 3D Viewer Sales",
    "summary": "Show in 3D button on sales orders (bridge between the 3D viewer and Sales)",
    "description": """
Factory 3D Viewer Sales
=======================

Small bridge between Factory 3D Viewer and Sales. It is installed automatically when both are present.

Key features
------------

* Adds the Show in 3D button to the sales order form
* Opens the 3D viewer for the selected order
""",
    "version": "19.0.1.0.1",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Manufacturing",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "depends": ["td_viewer3d", "sale"],
    "images": ["static/description/banner.png"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
}
