"""Очищення текстів журналу (SPEC R-14 п. 4)."""
import re

_CTRL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def clean_text(s, n=500):
    """Прибирає керівні символи `\\x00–\\x1f`, `\\x7f` (крім пробілу), стискає пробіли, обрізає до `n`."""
    if not s:
        return ""
    s = _CTRL.sub(" ", str(s))
    s = _SPACES.sub(" ", s).strip()
    return s[:n]
