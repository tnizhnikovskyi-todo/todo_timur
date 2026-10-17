"""R-20: серверне перетворення STEP/IGES/IFC у GLB (необов'язкові бібліотеки, DEC-04).

`CONVERTERS = {ext: (probe(), run(in_path, out_path, timeout))}` розширюється без змін ядра (тест підміняє словник).
Жодна бібліотека не обов'язкова: без них модель лишається `pending_conversion`.
"""
import shutil
import subprocess

CONVERT_TIMEOUT_S = 60
UNAVAILABLE_MESSAGE = (
    "Перетворення STEP/IFC на сервері недоступне: бібліотеку не встановлено (cascadio / IfcConvert). "
    "Оригінал збережено; експортуйте модель у GLB або OBJ.")
SERVER_FORMATS = ('step', 'stp', 'iges', 'igs', 'ifc')


def _probe_cascadio():
    try:
        import cascadio  # noqa: F401
    except ImportError:
        return False
    return True


def _run_cascadio(in_path, out_path, timeout):
    import cascadio
    cascadio.step_to_glb(in_path, out_path)  # ПРИПУЩЕННЯ щодо API cascadio (R-20)


def _probe_ifcconvert():
    return bool(shutil.which('IfcConvert'))


def _run_ifcconvert(in_path, out_path, timeout):
    subprocess.run(['IfcConvert', in_path, out_path], check=True, timeout=timeout, capture_output=True)


CONVERTERS = {
    'step': (_probe_cascadio, _run_cascadio),
    'stp': (_probe_cascadio, _run_cascadio),
    'ifc': (_probe_ifcconvert, _run_ifcconvert),
}


def available_converters():
    """{розширення: чи доступний конвертер}."""
    out = {}
    for ext in SERVER_FORMATS:
        entry = CONVERTERS.get(ext)
        out[ext] = bool(entry and entry[0]())
    return out
