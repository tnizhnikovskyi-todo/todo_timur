# Розширення `dispatch:` у звіті C-01

Додається до блоку з `flow-core/references/report-format.md` (`pr: null`). Вхід для C-02. Без ПІБ, контактів і змісту артефактів.

```yaml
dispatch:
  mode: on-complete            # dispatch | on-complete | sweep
  partial: false               # true, якщо оброблено частково (ліміт контексту)
  actions:
    - {action: created, step: A-11, scope: package/<id>, task_id: 1201, flow_map_row: 14, reason: "A-14 returned, FAIL pr-review"}
    - {action: held_slot, step: A-13, scope: package/<id>, reason: "слот 3/3"}
    - {action: skipped_stoplist, step: B-06, scope: client/cl-03, reason: "AI зупинено"}
    - {action: blocked, step: A-07, scope: package/<id>, task_id: 1188, reason: "2,5 x humanSla, raciA Власник продукту"}
  units_N: {D-01: 2}           # лише для кроків "на одиницю"
  skill_remarks:               # зауваження до скілів з гейтів; переносить у observations/ flow-state-keeper (C-02, експорт) своїм PR
    - {step: A-12, skill_ref: "flow-package-build:config-as-code@0.1.0", task_id: 1190, text: "..."}
```

`partial` і `held_slot` читає sweep (`sweep-rules.md` §1). `action`: created | requeued | reassigned | escalated | blocked | held_slot | skipped | skipped_stoplist | skipped_precondition.
