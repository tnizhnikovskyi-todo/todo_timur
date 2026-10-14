"""CLI: python -m iot_sim run|check-config|dump-catalog (SPEC §8.1.1)."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from iot_sim import __version__
from iot_sim.config import Settings


def cmd_check_config(settings: Settings) -> int:
    errors = settings.validate_required()
    catalog = Path(settings.catalog_dir) / "signals.csv"
    if not catalog.is_file():
        errors.append(f"немає каталогу {catalog}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if errors:
        return 2 if any("SIM_API_TOKEN" in e for e in errors) else 1
    print("config OK")
    return 0


def cmd_dump_catalog(settings: Settings) -> int:
    path = Path(settings.catalog_dir) / "signals.csv"
    with path.open(encoding="utf-8", newline="") as f:
        csv.writer(sys.stdout, lineterminator="\n").writerows(csv.reader(f))
    return 0


def cmd_run(settings: Settings) -> int:
    errors = settings.validate_required()
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2
    import uvicorn

    from iot_sim.protocols.control_api import create_app

    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port_control)  # noqa: S104
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="iot_sim")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("command", choices=["run", "check-config", "dump-catalog"])
    args = p.parse_args(argv)
    settings = Settings()
    handlers = {"run": cmd_run, "check-config": cmd_check_config, "dump-catalog": cmd_dump_catalog}
    return handlers[args.command](settings)


if __name__ == "__main__":
    sys.exit(main())
