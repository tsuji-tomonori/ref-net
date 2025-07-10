"""スケジュールタスク実装."""

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from celery import Task

from refnet_shared.celery_app import celery_app
from refnet_shared.models.database import Author, Paper, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from refnet_shared.utils.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


class CallbackTask(Task):
    """コールバック付きタスク基底クラス."""

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:
        """タスク成功時のコールバック."""
        logger.info("Task completed successfully", task_id=task_id, task_name=self.name)

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        """タスク失敗時のコールバック."""
        logger.error("Task failed", task_id=task_id, task_name=self.name, error=str(exc))


@celery_app.task(base=CallbackTask, name="refnet.scheduled.collect_new_papers")  # type: ignore[misc]
def collect_new_papers(max_papers: int = 100) -> dict[str, Any]:
    """新しい論文の収集."""
    logger.info("Starting scheduled paper collection", max_papers=max_papers)

    try:
        with db_manager.get_session() as session:
            # 未処理の論文IDを取得
            pending_papers = session.query(Paper).filter(Paper.crawl_status == "pending").limit(max_papers).all()

            collected_count = 0

            for paper in pending_papers:
                # クローラータスクをキューに追加
                try:
                    from refnet_crawler.tasks import crawl_paper_task  # type: ignore[import-not-found]

                    crawl_paper_task.delay(paper.paper_id)
                    collected_count += 1
                except ImportError:
                    logger.warning("Crawler tasks not available")
                    break

            logger.info("Paper collection scheduled", count=collected_count)

            return {"status": "success", "papers_scheduled": collected_count, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Failed to collect new papers", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.process_pending_summaries")  # type: ignore[misc]
def process_pending_summaries(batch_size: int = 50) -> dict[str, Any]:
    """未要約論文の処理."""
    logger.info("Starting scheduled summarization", batch_size=batch_size)

    try:
        with db_manager.get_session() as session:
            # 要約が必要な論文を取得
            papers_to_summarize = (
                session.query(Paper)
                .filter(Paper.crawl_status == "completed", Paper.summary_status == "pending", Paper.pdf_url.isnot(None))
                .limit(batch_size)
                .all()
            )

            processed_count = 0

            for paper in papers_to_summarize:
                # 要約タスクをキューに追加
                try:
                    from refnet_summarizer.tasks import summarize_paper_task  # type: ignore[import-not-found]

                    summarize_paper_task.delay(paper.paper_id)
                    processed_count += 1
                except ImportError:
                    logger.warning("Summarizer tasks not available")
                    break

            logger.info("Summarization tasks scheduled", count=processed_count)

            return {"status": "success", "summaries_scheduled": processed_count, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Failed to process pending summaries", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.generate_markdown_files")  # type: ignore[misc]
def generate_markdown_files(batch_size: int = 100) -> dict[str, Any]:
    """Markdownファイルの生成."""
    logger.info("Starting scheduled markdown generation", batch_size=batch_size)

    try:
        with db_manager.get_session() as session:
            # Markdown生成が必要な論文を取得
            papers_to_generate = session.query(Paper).filter(Paper.summary_status == "completed").limit(batch_size).all()

            generated_count = 0

            for paper in papers_to_generate:
                # 生成タスクをキューに追加
                try:
                    from refnet_generator.tasks import generate_markdown_task  # type: ignore[import-not-found]

                    generate_markdown_task.delay(paper.paper_id)
                    generated_count += 1
                except ImportError:
                    logger.warning("Generator tasks not available")
                    break

            logger.info("Markdown generation tasks scheduled", count=generated_count)

            return {"status": "success", "markdown_files_scheduled": generated_count, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Failed to generate markdown files", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.database_maintenance")  # type: ignore[misc]
def database_maintenance() -> dict[str, Any]:
    """データベースメンテナンス."""
    logger.info("Starting scheduled database maintenance")

    try:
        with db_manager.get_session() as session:
            maintenance_tasks = []

            # 古い処理キューエントリのクリーンアップ
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            deleted_queue_items = (
                session.query(ProcessingQueue)
                .filter(ProcessingQueue.created_at < cutoff_date, ProcessingQueue.status.in_(["completed", "failed"]))
                .delete()
            )

            if deleted_queue_items > 0:
                maintenance_tasks.append(f"Cleaned up {deleted_queue_items} old queue items")

            # 統計情報の更新
            from sqlalchemy import text
            session.execute(text("ANALYZE;"))
            maintenance_tasks.append("Updated database statistics")

            # 未使用インデックスの確認（ログのみ）
            # 実際の削除は手動で行う

            session.commit()

            logger.info("Database maintenance completed", tasks=maintenance_tasks)

            return {"status": "success", "maintenance_tasks": maintenance_tasks, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Database maintenance failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.system_health_check")  # type: ignore[misc]
def system_health_check() -> dict[str, Any]:
    """システムヘルスチェック."""
    logger.info("Starting system health check")

    try:
        health_status: dict[str, Any] = {"timestamp": datetime.utcnow().isoformat(), "services": {}, "metrics": {}, "overall_status": "healthy"}

        with db_manager.get_session() as session:
            # データベース接続チェック
            try:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
                health_status["services"]["database"] = "healthy"
            except Exception as e:
                health_status["services"]["database"] = f"unhealthy: {str(e)}"
                health_status["overall_status"] = "degraded"

            # Redis接続チェック
            try:
                from refnet_shared.middleware.rate_limiter import rate_limiter

                rate_limiter.redis_client.ping()
                health_status["services"]["redis"] = "healthy"
            except Exception as e:
                health_status["services"]["redis"] = f"unhealthy: {str(e)}"
                health_status["overall_status"] = "degraded"

            # データベースメトリクス取得
            total_papers = session.query(Paper).count()
            completed_summaries = session.query(Paper).filter(Paper.summary_status == "completed").count()

            health_status["metrics"] = {
                "total_papers": total_papers,
                "completed_summaries": completed_summaries,
                "completion_rate": completed_summaries / total_papers if total_papers > 0 else 0,
            }

            # メトリクスの更新
            status_counts: dict[str, dict[str, int]] = {"crawl": {}, "summary": {}, "pdf": {}}

            for status_type in status_counts.keys():
                column = getattr(Paper, f"{status_type}_status")
                for status in ["pending", "completed", "failed"]:
                    count = session.query(Paper).filter(column == status).count()
                    status_counts[status_type][status] = count

            MetricsCollector.update_paper_counts(total_papers, status_counts)

        logger.info("System health check completed", status=health_status["overall_status"])

        return health_status

    except Exception as e:
        logger.error("System health check failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.cleanup_old_logs")  # type: ignore[misc]
def cleanup_old_logs(days_to_keep: int = 30) -> dict[str, Any]:
    """古いログのクリーンアップ."""
    logger.info("Starting log cleanup", days_to_keep=days_to_keep)

    try:
        import glob

        log_dirs = ["/var/log/refnet", "/app/logs", "./logs"]
        cleaned_files = []
        total_size_freed = 0

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for log_file in glob.glob(f"{log_dir}/*.log*"):
                    file_path = Path(log_file)

                    # ファイル作成日時をチェック
                    if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_date:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                        total_size_freed += file_size

        logger.info("Log cleanup completed", files_cleaned=len(cleaned_files), size_freed_mb=total_size_freed / (1024 * 1024))

        return {
            "status": "success",
            "files_cleaned": len(cleaned_files),
            "size_freed_bytes": total_size_freed,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("Log cleanup failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.backup_database")  # type: ignore[misc]
def backup_database() -> dict[str, Any]:
    """データベースバックアップ."""
    logger.info("Starting database backup")

    try:
        from refnet_shared.config.environment import load_environment_settings

        settings = load_environment_settings()

        if not settings.is_production():
            logger.info("Skipping backup in non-production environment")
            return {"status": "skipped", "reason": "non-production environment", "timestamp": datetime.utcnow().isoformat()}

        # バックアップファイル名
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/backups/refnet_backup_{timestamp}.sql"

        # pg_dumpコマンド実行
        cmd = [
            "pg_dump",
            f"--host={settings.database.host}",
            f"--port={settings.database.port}",
            f"--username={settings.database.username}",
            f"--dbname={settings.database.database}",
            f"--file={backup_file}",
            "--no-password",
            "--verbose",
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.database.password or ""

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode == 0:
            # バックアップファイルサイズ取得
            backup_size = Path(backup_file).stat().st_size

            logger.info("Database backup completed", backup_file=backup_file, size_mb=backup_size / (1024 * 1024))

            return {"status": "success", "backup_file": backup_file, "size_bytes": backup_size, "timestamp": datetime.utcnow().isoformat()}
        else:
            logger.error("Database backup failed", error=result.stderr)
            return {"status": "error", "error": result.stderr, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Database backup failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=CallbackTask, name="refnet.scheduled.generate_stats_report")  # type: ignore[misc]
def generate_stats_report() -> dict[str, Any]:
    """統計レポート生成."""
    logger.info("Starting stats report generation")

    try:
        with db_manager.get_session() as session:
            # 基本統計
            total_papers = session.query(Paper).count()
            total_authors = session.query(Author).count()

            # 処理状況統計
            crawl_completed = session.query(Paper).filter(Paper.crawl_status == "completed").count()
            summary_completed = session.query(Paper).filter(Paper.summary_status == "completed").count()

            # 最近1週間の処理数
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_papers = session.query(Paper).filter(Paper.created_at >= week_ago).count()

            # 年別論文分布
            year_distribution = {}
            year_stats = session.query(Paper.year, Paper.year).group_by(Paper.year).all()
            for year, count in year_stats:
                if year:
                    year_distribution[str(year)] = count

            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "total_papers": total_papers,
                    "total_authors": total_authors,
                    "crawl_completion_rate": crawl_completed / total_papers if total_papers > 0 else 0,
                    "summary_completion_rate": summary_completed / total_papers if total_papers > 0 else 0,
                    "recent_papers_week": recent_papers,
                },
                "year_distribution": year_distribution,
                "processing_status": {
                    "crawl_completed": crawl_completed,
                    "summary_completed": summary_completed,
                    "crawl_pending": total_papers - crawl_completed,
                    "summary_pending": crawl_completed - summary_completed,
                },
            }

        # レポートファイル保存
        os.makedirs("/app/output", exist_ok=True)
        report_file = f"/app/output/stats_report_{datetime.utcnow().strftime('%Y%m%d')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("Stats report generated", report_file=report_file)

        return {"status": "success", "report_file": report_file, "stats": report["summary"], "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Stats report generation failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
