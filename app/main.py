from __future__ import annotations

import argparse
import sys

from app.agent_runtime import run_agent


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TV2MT5 Bridge")
    parser.add_argument("--agent", action="store_true", help="Run background agent process only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.agent:
        run_agent()
        return 0
    from app.bootstrap import build_container
    from app.ui.app import run_ui

    container = build_container()
    return run_ui(container.settings)


if __name__ == "__main__":
    raise SystemExit(main())
