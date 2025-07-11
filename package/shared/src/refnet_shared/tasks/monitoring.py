"""モニタリングタスク."""

from datetime import datetime

import httpx
import structlog

from refnet_shared.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(bind=True, name="refnet_shared.tasks.monitoring.health_check_all_services")
def health_check_all_services(self):
    """全サービスのヘルスチェック."""
    services = {
        "api": "http://api:8000/health",
        "crawler": "http://crawler:8001/health",
        "summarizer": "http://summarizer:8002/health",
        "generator": "http://generator:8003/health",
    }

    results = {}

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

    results["timestamp"] = datetime.utcnow().isoformat()

    # 異常があればアラート（将来的にSlack通知等）
    unhealthy_services = [s for s, r in results.items() if r.get("status") != "healthy"]
    if unhealthy_services:
        logger.warning("Unhealthy services detected", services=unhealthy_services)
        # TODO: アラート実装

    logger.info("Health check completed", results=results)
    return results
