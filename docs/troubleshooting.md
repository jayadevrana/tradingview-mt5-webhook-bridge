# Troubleshooting (Initial)

## UI does not start
- Ensure Python 3.11 is installed.
- Install dependencies with `pip install -e .[dev]`.
- On headless environments, PySide6 windows may fail to open.

## Agent cannot bind webhook port
- Port may already be in use.
- Change `TV2MT5_WEBHOOK_PORT` and restart.

## SQLite locked errors
- Keep single agent process active.
- Verify database is on local disk (not a network share).

## ngrok/MT5 not yet available
- Current delivery is Phase 1 scaffold.
- Concrete ngrok and MT5 execution implementations are scheduled for later phases.
