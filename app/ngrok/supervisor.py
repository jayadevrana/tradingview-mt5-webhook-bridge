from __future__ import annotations


class StubNgrokSupervisor:
    """Phase-1 process wiring placeholder."""

    def __init__(self) -> None:
        self._running = False

    def start(self, config: dict[str, object]) -> bool:
        _ = config
        self._running = False
        return False

    def stop(self, graceful_timeout_s: float = 5.0) -> None:
        _ = graceful_timeout_s
        self._running = False

    def health(self) -> dict[str, object]:
        return {"running": self._running, "reason": "Phase 1 scaffold"}

    def current_public_url(self) -> str | None:
        return None

