"""Python-реєстри точок розширення конструктора (MERGE.md §5.0).

`CHECKS`, `PLAN_BUILDERS`, `SNAPSHOT_SECTIONS`, `RENDERERS`.

Слайс реєструється зі СВОГО файлу (`services/<файл>.py` імпортується в `services/__init__.py`), спільний код не чіпає:

    from .registry import CHECKS

    @CHECKS.register('cell_load', sequence=80)
    def check_cell_load(scene, config, eps): ...

Реєстр порожній, доки слайси нічого не зареєстрували. Повторний ключ без `replace=True` — помилка (як у реєстрах ядра
JS, `core/constructor/registry.js`). Порядок обходу — за `sequence`, далі за порядком реєстрації.

Контракти значень (початкові; перший слайс, що підключає споживача, може їх уточнити у своїй задачі):

* `CHECKS`: `key -> fn(scene, config, eps) -> [issue]`, як у `checks.CHECKERS`; `issue = {check, severity, layer_id,
  codes, message}`; `key` збігається з `td.check.config.check_key`.
* `PLAN_BUILDERS`: `key -> fn(site, env, lines, issues) -> int`: дописує рядки плану R-12 і зауваження в
  `lines`/`issues` на місці, повертає число рядків «без змін».
* `SNAPSHOT_SECTIONS`: `key -> SnapshotSection(build, apply)`; `build(site) -> JSON-значення` розділу знімка,
  `apply(site, data)` відновлює його в чернетці (R-14); якщо розділу в знімку `schema: 1` немає, `apply` не
  викликається.
* `RENDERERS`: `key -> fn(env, payload) -> (filename, mimetype, content: bytes)` для API-19; ключі: `labels_pdf`,
  `table_xlsx`, `plan_pdf`, `spec_pdf`.
"""

from collections import namedtuple

SnapshotSection = namedtuple('SnapshotSection', ['build', 'apply'])


class RegistryError(ValueError):
    """Повторний ключ без `replace=True` або невідомий ключ у `unregister`."""


class Registry:
    def __init__(self, name):
        self.name = name
        self._items = {}  # key -> (sequence, order, value)
        self._order = 0

    def register(self, key, value=None, *, sequence=100, replace=False):
        """`register(key, value)` або декоратор `@REG.register(key)`; повертає значення."""
        if value is None:

            def decorator(func):
                self.register(key, func, sequence=sequence, replace=replace)
                return func

            return decorator
        if not isinstance(key, str) or not key:
            raise RegistryError("Реєстр %s: ключ має бути непорожнім рядком." % self.name)
        if key in self._items and not replace:
            raise RegistryError("Реєстр %s: ключ «%s» уже зареєстровано." % (self.name, key))
        self._order += 1
        self._items[key] = (sequence, self._order, value)
        return value

    def unregister(self, key):
        """Для тестів і заміни: прибирає запис (невідомий ключ — помилка)."""
        if key not in self._items:
            raise RegistryError("Реєстр %s: ключа «%s» немає." % (self.name, key))
        del self._items[key]

    def get(self, key, default=None):
        entry = self._items.get(key)
        return entry[2] if entry else default

    def _sorted(self):
        return sorted(self._items.items(), key=lambda kv: kv[1][:2])

    def keys(self):
        return [key for key, _entry in self._sorted()]

    def items(self):
        return [(key, entry[2]) for key, entry in self._sorted()]

    def values(self):
        return [entry[2] for _key, entry in self._sorted()]

    def __contains__(self, key):
        return key in self._items

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self.keys())

    def __repr__(self):
        return "<Registry %s: %s>" % (self.name, ", ".join(self.keys()) or "порожній")


CHECKS = Registry('CHECKS')
PLAN_BUILDERS = Registry('PLAN_BUILDERS')
SNAPSHOT_SECTIONS = Registry('SNAPSHOT_SECTIONS')
RENDERERS = Registry('RENDERERS')
