def post_init_hook(env):
    """SPEC §5.3: створити сигнали СКУД (пристрої data + 2 фіксовані); повторний виклик нічого не дублює."""
    env["td.access.telemetry"]._td_ensure_signals()
