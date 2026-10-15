"""Класифікація кодів подій BioStar 2 (R-09): code = main*256 + sub."""

_PASS_SUB = {
    0x10: lambda sub: 'pin' if sub == 1 else 'id_finger' if sub in (2, 3) else 'id_face' if sub in (4, 5)
    else 'card' if 6 <= sub <= 0x0B else 'other',
    0x13: lambda sub: 'finger' if sub in (1, 2) else 'face' if sub in (3, 4) else 'other',
}
_DENY = {1: 'access_group', 2: 'disabled', 3: 'expired', 4: 'blacklist', 5: 'apb', 6: 'timed_apb',
         7: 'scheduled_lock'}
_DOOR = {
    0x50: ('unlocked', 'Двері розблоковано'),
    0x51: ('locked', 'Двері зачинено на замок'),
    0x52: ('open', 'Двері відчинено'),
    0x53: ('closed', 'Двері зачинено'),
    0x54: ('forced', 'Двері відчинено силоміць'),
    0x55: ('held', 'Двері тримаються відчиненими'),
}


def _result(event_type, name, credential=False, deny_reason=False, door_state=False, alarm_reason=False):
    return {'event_type': event_type, 'credential': credential, 'deny_reason': deny_reason,
            'door_state': door_state, 'alarm_reason': alarm_reason, 'name': name}


def classify(code):
    """-> {'event_type', 'credential', 'deny_reason', 'door_state', 'alarm_reason', 'name'}."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0
    if code <= 0:
        return _result('other', 'Подія %s' % code)
    main, sub = code >> 8, code & 0xFF
    if main in _PASS_SUB:
        name = 'Успішна перевірка' if main == 0x10 else 'Успішна ідентифікація'
        return _result('pass', name, credential=_PASS_SUB[main](sub))
    if main == 0x11:
        return _result('fail', 'Невдала перевірка')
    if main in (0x12, 0x15):
        return _result('alarm', 'Прохід під примусом (duress)')
    if main in (0x14, 0x17, 0x18):
        return _result('fail', 'Невдала ідентифікація / автентифікація')
    if main == 0x16:
        return _result('pass', 'Подвійна автентифікація', credential='other')
    if main == 0x19:
        return _result('denied', 'Відмову в доступі', deny_reason=_DENY.get(sub, 'other'))
    if 0x20 <= main <= 0x2F:
        return _result('system', 'Керування користувачами/пристроєм')
    if 0x30 <= main <= 0x3F:
        return _result('system', 'Пристрій: запуск, мережа')
    if main in _DOOR:
        state, name = _DOOR[main]
        return _result('door', name, door_state=state,
                       alarm_reason=state if state in ('forced', 'held') else False)
    if 0x56 <= main <= 0x5F:
        return _result('door', 'Подія дверей')
    if 0x60 <= main <= 0x6F:
        return _result('alarm', 'Тривога зони', alarm_reason='fire' if code == 0x6700 else False)
    return _result('other', 'Подія %s' % code)
