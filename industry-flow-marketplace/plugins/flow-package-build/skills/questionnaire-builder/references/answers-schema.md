# Формат схеми і файлів відповідей `answers.yaml` (нормативний)

Власник формату — `flow-package-build:questionnaire-builder` (A-09). Його читають без власних парсерів:
`flow-core:flow-autocheck` (примітив `yaml-schema`, перевірки A-09), `flow-package-build:demo-base-builder` (A-15),
`flow-package-build:config-as-code` (A-12), `flow-package-build:package-release-builder` (A-18, diff ключів),
`flow-client-delivery:package-fit-gap` (B-02), `flow-client-delivery:runbook-executor` (B-04).
Зміна формату = нова `schema:` і окреме рішення Тімліда; скіл сам формат не змінює.

## 1. Три файли

| Файл | Що це | Хто пише |
|---|---|---|
| `package/templates/answers.yaml` | схема: що можна відповісти на кожну VP-xx | A-09 |
| `package/templates/answers.example.yaml` | плоска мапа `VP-xx: <default>` для всіх не-deprecated VP | A-09 |
| файл відповідей (`package/demo/answers.yaml`, `clients/<к>/answers.yaml`) | плоска мапа `VP-xx: <значення>` | A-15, B-02 (не цей скіл) |

## 2. Схема `answers.yaml`

Коментар-заголовок (обов'язковий, перші рядки файлу):
```yaml
# tr: docs/industries/<галузь>/ТР.md@<sha>
# schema: 1
```
Ключі верхнього рівня — **лише** `VP-\d{2,3}`, у порядку номерів. Метаданих-ключів немає.

| Поле | Обов'язкове | Зміст |
|---|---|---|
| `param` | так | назва параметра дослівно з ТР |
| `question` | так для не-deprecated | `Q-NN` з `questionnaire.md`; для deprecated — відсутнє |
| `type` | так | `enum` (одне зі списку), `multi` (підмножина списку), `bool` (`true`/`false`), `int` |
| `allowed` | так для `enum`/`multi` | список значень дослівно з таблиці VP ТР (не перефразовувати) |
| `min`, `max`, `unit` | лише `int`, лише якщо ТР дає діапазон | числа / одиниця |
| `default` | так для не-deprecated | `enum` — один елемент `allowed`; `multi` — список (підмножина `allowed`); `bool`; `int` у `min..max` |
| `default_from` | так | `tr` (default є в ТР) або `ai` (запропонований, рішення Тімліда) |
| `ac` | так | список `AC-xx` з ТР (може бути порожнім `[]`, якщо ТР не зв'язує) |
| `applies_if` | лише якщо ТР задає залежність | `{VP-xx: <значення>}`: VP актуальна, лише коли інша VP має це значення; посилання на наявну VP |
| `deprecated` | так | `false` або рядок `"з версії X.Y"` |

Життєвий цикл `deprecated`: у версії X.Y, де ТР позначило VP, ключ лишається з `deprecated: "з версії X.Y"`,
питання вилучається з анкети, у `answers.example.yaml` її немає. На **наступному** тегу ключ видаляється.
Значення `уточнити` у схемі й example заборонене (його ставить лише B-02 у файлі відповідей клієнта).

## 3. `answers.example.yaml`
```yaml
VP-01: make_to_order
VP-02: true
```
Усі не-deprecated VP схеми, значення = `default`; жодних зайвих ключів і коментарів-даних клієнта.

## 4. Приклад схеми (вигаданий, 4 VP меблевого виробництва)
```yaml
# tr: docs/industries/furniture/ТР.md@0000000
# schema: 1
VP-01:
  param: Стратегія виконання замовлень
  question: Q-01
  type: enum
  allowed: [make_to_order, make_to_stock, mixed]
  default: make_to_order
  default_from: tr
  ac: [AC-01, AC-02]
  deprecated: false
VP-02:
  param: Облік залишків плитних матеріалів
  question: Q-02
  type: bool
  default: true
  default_from: tr
  ac: [AC-03]
  deprecated: false
VP-03:
  param: Кількість складів
  question: Q-03
  type: int
  min: 1
  max: 5
  unit: складів
  default: 1
  default_from: ai
  ac: []
  deprecated: false
VP-04:
  param: Типи виробів
  question: Q-04
  type: multi
  allowed: [cabinet, kitchen, office]
  default: [cabinet]
  default_from: tr
  ac: [AC-05]
  applies_if: {VP-01: mixed}
  deprecated: false
```
Значення `allowed` — технічні ключі з ТР; людські назви варіантів — лише в `questionnaire.md` (відповідність 1:1).
