# Формат виходу flow-autocheck

## JSON (`<tmp>/autocheck/<step>-<scope>-<attempt>.json`)
```json
{
  "mode": "result", "step": "A-10", "scope": "package/<id>", "base_sha": "<sha>", "head_sha": "<sha>",
  "spec_version": "<версія плагіна>", "verdict": "FAIL",
  "checks": [
    {"id": "ac-coverage", "status": "FAIL", "msg": "Додай рядок для AC-03 у package/ALLOCATION.md: трек і модуль Odoo",
     "evidence": "package/ALLOCATION.md", "route_on_fail": null},
    {"id": "module-source", "status": "MANUAL", "msg": "Модуль існує для Odoo 19 у редакції A-07 (Архітектор рішення)", "evidence": "", "route_on_fail": null}
  ]
}
```
`status` ∈ PASS, FAIL, WARN, SKIP, ERROR, MANUAL. `verdict` ∈ PASS, FAIL, INCOMPLETE. `evidence` — `шлях:рядок` або SHA, до 200 символів, без витягів
з клієнтських файлів. `checks[]` вставляється в звіт 1:1 (`flow-core/references/report-format.md`); `autocheck: {verdict, spec_version}` — окреме поле звіту.

## Таблиця md
`| ID | Статус | Що перевірено | Помилка (для повтору) | Повернення |` — спочатку FAIL і ERROR, потім WARN, MANUAL, SKIP, PASS.
Після таблиці — блок «Для чек-листа гейта» (MANUAL дослівно). Повернення — «пропозиція, рішення — людина».

## Правило тексту помилки
Імператив, самодостатній, з ID і шляхом: «Додай…», «Виправ трек AC-05 з hybrid на один із {стандарт, конфіг, код, готове}».
Без загальних фраз («є розбіжності») і без вигаданих значень.
