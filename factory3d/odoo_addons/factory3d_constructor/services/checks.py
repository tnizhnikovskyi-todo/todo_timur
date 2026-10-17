"""R-04…R-10: перевірки розкладки (чистий Python). Повна реалізація — у наступному коміті."""

CHECK_KEYS = ['fits', 'collide', 'service_free', 'aisles_free', 'load', 'utility_reach', 'fire']

CHECK_LABELS = {
    'fits': "Вміщується",
    'collide': "Перетини",
    'service_free': "Зона обслуговування вільна",
    'aisles_free': "Проходи вільні",
    'load': "Навантаження",
    'utility_reach': "Досяжність підключення",
    'fire': "Пожежні проходи й виходи",
}

# R-04: (check_key, enabled, mode, params), sequence = 10…70 за порядком
CHECK_DEFAULTS = [
    ('fits', True, 'block', {}),
    ('collide', True, 'block', {}),
    ('service_free', True, 'warn', {}),
    ('aisles_free', True, 'block', {}),
    ('load', True, 'warn', {}),
    ('utility_reach', True, 'warn', {'max_m': 15}),
    ('fire', True, 'block', {}),
]
