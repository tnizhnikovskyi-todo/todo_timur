# Схема `src/screens.json`

Оболонка читає цей файл і малює екрани; HTML агент не пише. Невалідний JSON або посилання на неіснуючий
екран/поле — помилка `assemble.mjs`.

## Верхній рівень
```json
{
  "package": "<назва пакета>",
  "start": "S-01",
  "roles": [{"id": "ROLE-01", "name": "Менеджер замовлень", "home": "S-01"}],
  "screens": [ /* екрани */ ]
}
```

## Екран
| Ключ | Зміст |
|---|---|
| `id` | `S-xx` зі `screens.md`; маршрут `#/S-xx` |
| `title` | назва з `screens.md` |
| `type` | `list` / `form` / `kanban` / `dashboard` / `wizard` |
| `model` | сутність з `data/demo-data.json` (для list/form/kanban) |
| `fields` | поля: `{name, label, kind: char\|number\|date\|select\|m2o\|status, comodel? (обов'язково для m2o), readonly?, calc?}` |
| `statusbar` | для form: впорядковані стани сутності |
| `columns` / `group_by` | для list / kanban |
| `actions` | кнопки й переходи: `{testid, label, go: "S-xx", set: {поле: значення}, create: "<model>"}` |
| `added_for` | лише для доданих екранів: `"SC-xx"` (позначка «додано для SC-xx, немає в screens.md») |

## `calc` (імітація розрахунку)
```json
{"id": "CALC-01", "formula": "qty * unit_price * (1 - discount)", "inputs": ["qty", "unit_price", "discount"],
 "hint": "[Імітація] сума рахується за спрощеною формулою; у пакеті — логіка td_*"}
```
- `formula` — лише арифметика над `inputs`; без викликів, циклів, зовнішніх даних.
- `hint` обов'язково починається з «[Імітація]» і показується біля поля.
- Кожен `calc.id` має рядок у колонці «Імітація в прототипі» `complexity.md` (VP-imitation).
- Складна логіка (розкрій, планування) — підставлений результат з даних, `formula: "const"`, з тим самим `hint`.

## `data/demo-data.json`
```json
{"seed": 2026, "reference_date": "2026-01-15", "entities": {"customer": [{"id": "c1", "name": "Демо-Клієнт 01", "reg_code": "ДЕМО-0001"}],
 "order": [{"id": "o1", "name": "Демо-Замовлення 001", "customer": "c1", "state": "нове"}]}}
```
`entities.<model>` — масив записів з унікальним `id`; `m2o` — `id` запису `comodel`; `state` — поточний статус для `statusbar`/kanban.

## Що малює оболонка (`data-testid`)
`screen-title`, `statusbar-current`, `state-<значення>`, `field-<name>`, `hint-<name>`, `row-<id>`, `card-<id>`, `tile-<name>`,
`role-switch`, `banner`. Клік по рядку/картці відкриває форму тієї ж моделі. `set` змінює поточний запис, `create` додає
запис, `go` переходить на екран (`assemble.mjs` перевіряє, що екран існує).

## Правила
- `data-testid` = `actions[].testid`, унікальний у межах екрана; spec-файли посилаються лише на нього.
- Кожен крок кожного сценарію має дію або поле, на яке спирається очікування.
- Назви полів і підписів — з `concept/`; своїх термінів не вводити.

## Приклад (скорочено)
```json
{"id": "S-02", "title": "Замовлення", "type": "form", "model": "order",
 "statusbar": ["нове", "у виробництві", "готове", "відвантажене"],
 "fields": [
  {"name": "customer", "label": "Клієнт", "kind": "m2o", "comodel": "customer"},
  {"name": "total", "label": "Сума", "kind": "number", "readonly": true,
   "calc": {"id": "CALC-01", "formula": "qty * unit_price", "inputs": ["qty", "unit_price"],
            "hint": "[Імітація] спрощений розрахунок суми"}}],
 "actions": [{"testid": "order-confirm", "label": "Підтвердити", "set": {"state": "у виробництві"}, "go": "S-03"}]}
```
