# td_genset_factory3d

Міст між `td_genset` і моделлю заводу (telemetry, energy, обслуговування, 3D-картка). Залежності: `td_genset`,
`td_factory3d`, `td_telemetry`, `td_energy`; `td_viewer3d` необов'язковий.

Статус: W0 — каркас (маніфест, параметри `td.genset.*`, адаптер `adapters/td_genset.py` із заглушками ADP-01…ADP-10,
`neutralize.sql`). Моделі, дані, крони й представлення — W2/W3.

Підключення генератора: після W2 — через `td.genset3d.link` (обладнання GENSET + профіль).
