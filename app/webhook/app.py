from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.webhook.service import WebhookIntakeService


def create_webhook_app(
    service: WebhookIntakeService,
    mt5_status_provider: Callable[[], dict[str, Any]] | None = None,
) -> FastAPI:
    app = FastAPI(title="TV2MT5 Bridge Agent", version="0.2.0")
    app.state.intake_service = service
    app.state.mt5_status_provider = mt5_status_provider or (lambda: {"ok": False, "message": "not configured"})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook/{endpoint_token}")
    async def webhook_intake(endpoint_token: str, request: Request) -> JSONResponse:
        raw_body = await request.body()
        source_ip = request.client.host if request.client else None
        intake_service: WebhookIntakeService = request.app.state.intake_service
        result = intake_service.handle_request(
            endpoint_token=endpoint_token,
            raw_body=raw_body,
            source_ip=source_ip,
        )
        return JSONResponse(status_code=result.http_status, content=result.body)

    @app.get("/mt5/status")
    def mt5_status(request: Request) -> dict[str, Any]:
        provider: Callable[[], dict[str, Any]] = request.app.state.mt5_status_provider
        return provider()

    return app


def build_test_webhook_app(
    service: WebhookIntakeService,
    mt5_status_provider: Callable[[], dict[str, Any]] | None = None,
) -> FastAPI:
    return create_webhook_app(service, mt5_status_provider=mt5_status_provider)
