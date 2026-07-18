# Folder Structure

```text
TV2MT5-Bridge/
  app/
    core/          # constants, app paths, shared utility types
    config/        # typed settings and config loader
    db/            # SQLAlchemy engine/session/models + SQL migrations
    domain/        # business enums/models/interface contracts
    webhook/       # FastAPI app and HTTP-facing contracts
    queue/         # queue repository + queue service shell
    mt5/           # MT5 adapter abstraction and implementations
    ngrok/         # ngrok supervisor abstraction and implementations
    license/       # licensing abstraction and implementations
    logging/       # structured logging setup/formatters
    ui/            # PySide6 application shell and screens
    main.py        # process bootstrap entrypoint
  docs/
    architecture.md
    database-schema.md
    interface-contracts.md
    phased-implementation-plan.md
    troubleshooting.md
  tests/
    unit/
    integration/
  samples/
    payloads/
  scripts/
    build_windows_exe.ps1
  pyproject.toml
  README.md
```
