from __future__ import annotations

import uvicorn

from app.bootstrap import build_container
from app.mt5.status_service import MT5StatusService
from app.webhook.app import create_webhook_app
from app.webhook.service import WebhookIntakeService


def run_agent() -> None:
    container = build_container()
    service = WebhookIntakeService(
        session_factory=container.session_factory,
        endpoint_token=container.settings.agent.endpoint_token,
        payload_secret=container.settings.agent.payload_secret,
    )
    mt5_status_service = MT5StatusService()
    app = create_webhook_app(service, mt5_status_provider=mt5_status_service.snapshot)
    uvicorn.run(
        app,
        host=container.settings.agent.host,
        port=container.settings.agent.port,
        log_level=container.settings.agent.log_level.lower(),
    )
