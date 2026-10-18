# factory3d_genset

Міст між `td_genset` і моделлю заводу (telemetry, energy, обслуговування, 3D-картка). Залежності: `td_genset`,
`factory3d_base`, `factory3d_telemetry`, `factory3d_energy`; `factory3d_viewer` необов'язковий.

Статус: W0 — каркас (маніфест, параметри `factory3d.genset.*`, адаптер `adapters/td_genset.py` із заглушками ADP-01…ADP-10,
`neutralize.sql`). Моделі, дані, крони й представлення — W2/W3.

Підключення генератора: після W2 — через `f3d.genset.link` (обладнання GENSET + профіль).
