# ruff: noqa: B018
{
    "name": "Access Telemetry Bridge",
    "summary": "Seven access/* access-control signals in telemetry",
    "description": """
Access Telemetry Bridge
=======================

Bridge between Factory Access Control and Factory 3D Telemetry, installed automatically when both are present.

Key features
------------

* Publishes seven access control signals as telemetry signals
""",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_access", "td_telemetry"],
    "images": ["static/description/banner.png"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
