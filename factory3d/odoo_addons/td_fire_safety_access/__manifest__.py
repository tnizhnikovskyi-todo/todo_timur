{
    "name": "Fire Safety Access Bridge",
    "summary": "Evacuation doors in the access control system and release of drill locks",
    "description": """
Fire Safety Access Bridge
=========================

Bridge between Fire Safety and Access Control, installed automatically when both are present. It adds no models of its own.

Key features
------------

* Emergency exit doors EX-* in the access control system, so that every person who leaves through an exit is seen: the drill report shows who left by an exit other than the one assigned to their zone route
* After a training alarm ends, the locks left by the alarm cascade are released: doors unlocked by the alarm are locked again and the fire alarm of the doors is acknowledged (a real alarm is never touched)
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "support": "support@todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_fire_safety", "td_access"],
    "images": ["static/description/banner.png"],
    "data": ["data/td_access_exit_doors.xml"],
    "installable": True,
    "auto_install": True,
    "application": False,
}
