"""RefNet Generator メインエントリーポイント."""

import sys

import structlog

logger = structlog.get_logger(__name__)


def main() -> None:
    """メインエントリーポイント."""
    logger.info("RefNet Generator Service", version="0.1.0")
    logger.info("Use 'celery worker' command to start the worker")
    sys.exit(0)


if __name__ == "__main__":
    main()
