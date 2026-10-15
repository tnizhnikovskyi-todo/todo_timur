"""Часові пояси (SPEC §11): у БД — UTC naive; тексти й payload — Europe/Kyiv."""
from datetime import timezone
from zoneinfo import ZoneInfo

try:
    KYIV = ZoneInfo("Europe/Kyiv")
except Exception:  # старий tzdata
    KYIV = ZoneInfo("Europe/Kiev")


def local(dt, fmt="%Y-%m-%d %H:%M"):
    """UTC naive datetime → рядок «YYYY-MM-DD HH:MM» за Києвом; порожнє → ''."""
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime(fmt)
