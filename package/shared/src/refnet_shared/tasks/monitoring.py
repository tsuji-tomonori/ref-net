"""モニタリングタスク."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from refnet_shared.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, name="refnet_shared.tasks.monitoring.health_check_all_services")  # type: ignore[misc]
def health_check_all_services(self: Any) -> dict:
    """全サービスのヘルスチェック."""
    services = {
        "api": "http://api:8000/health",
        "crawler": "http://crawler:8001/health",
        "summarizer": "http://summarizer:8002/health",
        "generator": "http://generator:8003/health",
    }

    results: dict[str, dict[str, str | int | float]] = {}

    for service_name, url in services.items():
        try:
            response = httpx.get(url, timeout=5.0)
            results[service_name] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
            }
        except Exception as e:
            results[service_name] = {
                "status": "error",
                "error": str(e),
            }

    # 異常があればアラート（将来的にSlack通知等）
    unhealthy_services = [
        s for s, r in results.items()
        if isinstance(r, dict) and r.get("status") != "healthy"
    ]
    if unhealthy_services:
        logger.warning("Unhealthy services detected", services=unhealthy_services)
        # TODO: アラート実装

    logger.info("Health check completed", results=results)

    # Add timestamp
    timestamp_dict = {"timestamp": datetime.utcnow().isoformat()}
    return {**results, **timestamp_dict}
