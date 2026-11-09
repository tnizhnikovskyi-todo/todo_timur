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
| `fields` | поля: `{name, label, kind: char\|number\|date\|select\|m2o\|status, readonly?, calc?}` |
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

## Правила
- `data-testid` = `actions[].testid`, унікальний у межах екрана; spec-файли посилаються лише на нього.
- Кожен крок кожного сценарію має дію або поле, на яке спирається очікування.
- Назви полів і підписів — з `concept/`; своїх термінів не вводити.

## Приклад (скорочено)
```json
{"id": "S-02", "title": "Замовлення", "type": "form", "model": "order",
 "statusbar": ["нове", "у виробництві", "готове", "відвантажене"],
 "fields": [
  {"name": "customer", "label": "Клієнт", "kind": "m2o"},
  {"name": "total", "label": "Сума", "kind": "number", "readonly": true,
   "calc": {"id": "CALC-01", "formula": "qty * unit_price", "inputs": ["qty", "unit_price"],
            "hint": "[Імітація] спрощений розрахунок суми"}}],
 "actions": [{"testid": "order-confirm", "label": "Підтвердити", "set": {"state": "у виробництві"}, "go": "S-03"}]}
```
