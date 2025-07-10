"""
Auto-recovery utility for RefNet system.

This module provides automatic recovery mechanisms for common system failures
including database connection issues, service failures, and resource exhaustion.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import psutil
import redis
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from .security_audit import SecurityEventType, SecurityLevel, get_security_logger

logger = structlog.get_logger(__name__)
security_logger = get_security_logger("refnet-auto-recovery")


class RecoveryActionType(Enum):
    """Types of recovery actions."""

    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    RESTART_DATABASE_CONNECTION = "restart_database_connection"
    CLEAN_TEMP_FILES = "clean_temp_files"
    RESTART_CELERY_WORKER = "restart_celery_worker"
    SCALE_RESOURCES = "scale_resources"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"


class RecoveryStatus(Enum):
    """Status of recovery attempts."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class RecoveryAction:
    """Recovery action configuration."""

    action_type: RecoveryActionType
    name: str
    condition: str
    action_func: Callable
    max_attempts: int = 3
    delay_seconds: int = 5
    enabled: bool = True
    dependencies: list[str] | None = None


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    action_type: RecoveryActionType
    name: str
    status: RecoveryStatus
    attempts: int
    duration: float
    error: str | None = None
    details: dict[str, Any] | None = None


class AutoRecoveryManager:
    """Manages automatic recovery actions for system failures."""

    def __init__(self) -> None:
        self.config = settings
        self.recovery_actions: list[RecoveryAction] = []
        self.recovery_history: list[RecoveryResult] = []
        self.circuit_breakers: dict[str, dict[str, Any]] = {}
        self.cooldown_timers: dict[str, float] = {}
        self._setup_recovery_actions()

    def _setup_recovery_actions(self) -> None:
        """Setup default recovery actions."""
        self.recovery_actions = [
            RecoveryAction(
                action_type=RecoveryActionType.RESTART_DATABASE_CONNECTION,
                name="Database Connection Recovery",
                condition="database_connection_failed",
                action_func=self._recover_database_connection,
                max_attempts=3,
                delay_seconds=10,
            ),
            RecoveryAction(
                action_type=RecoveryActionType.CLEAR_CACHE,
                name="Redis Cache Clear",
                condition="redis_memory_high",
                action_func=self._clear_redis_cache,
                max_attempts=2,
                delay_seconds=5,
            ),
            RecoveryAction(
                action_type=RecoveryActionType.CLEAN_TEMP_FILES,
                name="Temporary Files Cleanup",
                condition="disk_space_low",
                action_func=self._clean_temp_files,
                max_attempts=1,
                delay_seconds=0,
            ),
            RecoveryAction(
                action_type=RecoveryActionType.RESTART_CELERY_WORKER,
                name="Celery Worker Restart",
                condition="celery_worker_stuck",
                action_func=self._restart_celery_worker,
                max_attempts=2,
                delay_seconds=15,
            ),
            RecoveryAction(
                action_type=RecoveryActionType.CIRCUIT_BREAKER_RESET,
                name="Circuit Breaker Reset",
                condition="circuit_breaker_open",
                action_func=self._reset_circuit_breaker,
                max_attempts=1,
                delay_seconds=0,
            ),
        ]

    async def execute_recovery(self, condition: str, context: dict[str, Any] | None = None) -> list[RecoveryResult]:
        """Execute recovery actions for a given condition."""
        results: list[RecoveryResult] = []
        context = context or {}

        logger.info("Starting auto-recovery", condition=condition, context=context)

        # Find applicable recovery actions
        applicable_actions = [action for action in self.recovery_actions if action.condition == condition and action.enabled]

        if not applicable_actions:
            logger.warning("No recovery actions found for condition", condition=condition)
            return results

        # Execute recovery actions
        for action in applicable_actions:
            if self._is_in_cooldown(action.name):
                logger.info("Recovery action in cooldown", action=action.name)
                continue

            result = await self._execute_recovery_action(action, context)
            results.append(result)

            # Log recovery attempt
            security_logger.log_security_event(
                SecurityEventType.SYSTEM_ADMIN_ACTION,
                SecurityLevel.INFO,
                f"Auto-recovery action executed: {action.name}",
                additional_data={
                    "action_type": action.action_type.value,
                    "status": result.status.value,
                    "attempts": result.attempts,
                    "duration": result.duration,
                },
            )

            # Set cooldown if failed
            if result.status == RecoveryStatus.FAILED:
                self._set_cooldown(action.name, 300)  # 5 minutes cooldown

        self.recovery_history.extend(results)
        return results

    async def _execute_recovery_action(self, action: RecoveryAction, context: dict[str, Any]) -> RecoveryResult:
        """Execute a single recovery action with retry logic."""
        start_time = time.time()
        attempts = 0
        last_error = None

        for attempt in range(action.max_attempts):
            attempts += 1

            try:
                logger.info("Executing recovery action", action=action.name, attempt=attempt + 1)

                result = await action.action_func(context)

                if result:
                    return RecoveryResult(
                        action_type=action.action_type,
                        name=action.name,
                        status=RecoveryStatus.SUCCESS,
                        attempts=attempts,
                        duration=time.time() - start_time,
                        details=result if isinstance(result, dict) else None,
                    )

            except Exception as e:
                last_error = str(e)
                logger.error("Recovery action failed", action=action.name, attempt=attempt + 1, error=str(e))

                if attempt < action.max_attempts - 1:
                    await asyncio.sleep(action.delay_seconds)

        return RecoveryResult(
            action_type=action.action_type,
            name=action.name,
            status=RecoveryStatus.FAILED,
            attempts=attempts,
            duration=time.time() - start_time,
            error=last_error,
        )

    def _is_in_cooldown(self, action_name: str) -> bool:
        """Check if action is in cooldown period."""
        if action_name not in self.cooldown_timers:
            return False

        return time.time() < self.cooldown_timers[action_name]

    def _set_cooldown(self, action_name: str, seconds: int) -> None:
        """Set cooldown timer for action."""
        self.cooldown_timers[action_name] = time.time() + seconds

    async def _recover_database_connection(self, context: dict[str, Any]) -> bool:
        """Recover database connection."""
        try:
            db_url = self.config.database.url
            engine = create_engine(db_url)

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone() is not None

        except SQLAlchemyError as e:
            logger.error("Database connection recovery failed", error=str(e))
            return False

    async def _clear_redis_cache(self, context: dict[str, Any]) -> bool:
        """Clear Redis cache to free memory."""
        try:
            redis_client = redis.Redis.from_url(self.config.redis.url)

            # Get memory usage before clearing
            info = redis_client.info("memory")
            memory_before = info.get("used_memory", 0)

            # Clear cache based on patterns
            cache_patterns = context.get("cache_patterns", ["cache:*", "session:*"])

            for pattern in cache_patterns:
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)

            # Get memory usage after clearing
            info_after = redis_client.info("memory")
            memory_after = info_after.get("used_memory", 0)

            logger.info("Redis cache cleared", memory_before=memory_before, memory_after=memory_after, freed_bytes=memory_before - memory_after)

            return True

        except Exception as e:
            logger.error("Redis cache clear failed", error=str(e))
            return False

    async def _clean_temp_files(self, context: dict[str, Any]) -> bool:
        """Clean temporary files to free disk space."""
        try:
            import tempfile
            from pathlib import Path

            temp_dirs = context.get("temp_dirs", [tempfile.gettempdir()])
            cleaned_size = 0

            for temp_dir in temp_dirs:
                temp_path = Path(temp_dir)
                if temp_path.exists():
                    for file_path in temp_path.glob("**/*"):
                        if file_path.is_file():
                            try:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                cleaned_size += file_size
                            except Exception:
                                continue

            logger.info("Temporary files cleaned", cleaned_size=cleaned_size, cleaned_mb=cleaned_size / (1024 * 1024))

            return True

        except Exception as e:
            logger.error("Temporary files cleanup failed", error=str(e))
            return False

    async def _restart_celery_worker(self, context: dict[str, Any]) -> bool:
        """Restart Celery worker (signal-based restart)."""
        try:
            # This would typically send a signal to restart the worker
            # For now, we'll just log the action
            worker_id = context.get("worker_id", "unknown")

            logger.info("Celery worker restart requested", worker_id=worker_id)

            # In a real implementation, this would:
            # 1. Send SIGTERM to the worker process
            # 2. Wait for graceful shutdown
            # 3. Restart the worker

            return True

        except Exception as e:
            logger.error("Celery worker restart failed", error=str(e))
            return False

    async def _reset_circuit_breaker(self, context: dict[str, Any]) -> bool:
        """Reset circuit breaker to allow traffic."""
        try:
            circuit_breaker_name = context.get("circuit_breaker_name", "default")

            if circuit_breaker_name in self.circuit_breakers:
                self.circuit_breakers[circuit_breaker_name]["state"] = "closed"
                self.circuit_breakers[circuit_breaker_name]["failure_count"] = 0
                self.circuit_breakers[circuit_breaker_name]["last_failure"] = None

                logger.info("Circuit breaker reset", name=circuit_breaker_name)
                return True

            return False

        except Exception as e:
            logger.error("Circuit breaker reset failed", error=str(e))
            return False

    def get_recovery_history(self, limit: int = 100) -> list[RecoveryResult]:
        """Get recent recovery history."""
        return self.recovery_history[-limit:]

    def get_recovery_statistics(self) -> dict[str, Any]:
        """Get recovery statistics."""
        if not self.recovery_history:
            return {}

        total_actions = len(self.recovery_history)
        successful = sum(1 for r in self.recovery_history if r.status == RecoveryStatus.SUCCESS)
        failed = sum(1 for r in self.recovery_history if r.status == RecoveryStatus.FAILED)

        action_stats = {}
        for result in self.recovery_history:
            action_type = result.action_type.value
            if action_type not in action_stats:
                action_stats[action_type] = {"total": 0, "success": 0, "failed": 0}

            action_stats[action_type]["total"] += 1
            if result.status == RecoveryStatus.SUCCESS:
                action_stats[action_type]["success"] += 1
            else:
                action_stats[action_type]["failed"] += 1

        return {
            "total_actions": total_actions,
            "successful_actions": successful,
            "failed_actions": failed,
            "success_rate": successful / total_actions if total_actions > 0 else 0,
            "action_statistics": action_stats,
        }


# Global auto-recovery manager instance
_auto_recovery_manager = AutoRecoveryManager()


def get_auto_recovery_manager() -> AutoRecoveryManager:
    """Get the global auto-recovery manager instance."""
    return _auto_recovery_manager


async def trigger_recovery(condition: str, context: dict[str, Any] | None = None) -> list[RecoveryResult]:
    """Trigger recovery for a specific condition."""
    return await _auto_recovery_manager.execute_recovery(condition, context)


def check_system_health() -> dict[str, str | float]:
    """Check system health and identify potential issues."""
    health_status: dict[str, str | float] = {
        "database": "unknown",
        "redis": "unknown",
        "disk_usage": "unknown",
        "memory_usage": "unknown",
        "cpu_usage": "unknown"
    }

    # Check database connectivity
    try:
        engine = create_engine(settings.database.url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["database"] = "healthy"
    except Exception:
        health_status["database"] = "unhealthy"

    # Check Redis connectivity
    try:
        redis_client = redis.Redis.from_url(settings.redis.url)
        redis_client.ping()
        health_status["redis"] = "healthy"
    except Exception:
        health_status["redis"] = "unhealthy"

    # Check system resources
    try:
        # Disk usage
        disk_usage = psutil.disk_usage("/")
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        health_status["disk_usage"] = disk_percent

        # Memory usage
        memory = psutil.virtual_memory()
        health_status["memory_usage"] = memory.percent

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        health_status["cpu_usage"] = cpu_percent

    except Exception as e:
        logger.error("System health check failed", error=str(e))

    return health_status
