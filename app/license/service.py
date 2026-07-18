from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import LicenseStatus
from app.domain.models import LicenseState


class StubLicenseService:
    """Phase-1 license interface placeholder (no live activation)."""

    def activate(self, license_key: str, machine_fingerprint: str) -> LicenseState:
        _ = license_key
        _ = machine_fingerprint
        return LicenseState(status=LicenseStatus.INVALID.value, message="Activation not available in Phase 1")

    def refresh(self) -> LicenseState:
        return self.current_state()

    def current_state(self) -> LicenseState:
        return LicenseState(
            status=LicenseStatus.INVALID.value,
            message="License service not connected",
            valid_until=datetime.now(timezone.utc),
        )
