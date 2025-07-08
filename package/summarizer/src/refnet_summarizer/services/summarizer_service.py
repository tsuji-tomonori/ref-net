"""要約サービス."""

from datetime import datetime

import structlog
from refnet_shared.models.database import Paper, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from sqlalchemy.orm import Session

from refnet_summarizer.clients.ai_client import create_ai_client
from refnet_summarizer.processors.pdf_processor import PDFProcessor

logger = structlog.get_logger(__name__)


class SummarizerService:
    """要約サービス."""

    def __init__(self) -> None:
        """初期化."""
        self.pdf_processor = PDFProcessor()
        self.ai_client = create_ai_client()

    async def summarize_paper(self, paper_id: str) -> bool:
        """論文要約処理."""
        try:
            with db_manager.get_session() as session:
                # 論文情報取得
                paper = session.query(Paper).filter_by(paper_id=paper_id).first()
                if not paper:
                    logger.warning("Paper not found", paper_id=paper_id)
                    return False

                # PDF URL チェック
                if not paper.pdf_url:
                    logger.warning("No PDF URL available", paper_id=paper_id)
                    await self._update_processing_status(
                        session, paper_id, "summary", "failed", "No PDF URL"
                    )
                    return False

                # PDF ダウンロードとテキスト抽出
                pdf_content = await self.pdf_processor.download_pdf(paper.pdf_url)
                if not pdf_content:
                    logger.warning("Failed to download PDF", paper_id=paper_id)
                    await self._update_processing_status(
                        session, paper_id, "summary", "failed", "PDF download failed"
                    )
                    return False

                # PDF 情報の更新
                paper.pdf_hash = self.pdf_processor.calculate_hash(pdf_content)
                paper.pdf_size = len(pdf_content)
                paper.pdf_status = "completed"

                # テキスト抽出
                text = self.pdf_processor.extract_text(pdf_content)
                if not text or len(text) < 100:
                    logger.warning(
                        "Failed to extract text or text too short",
                        paper_id=paper_id,
                        text_length=len(text),
                    )
                    await self._update_processing_status(
                        session, paper_id, "summary", "failed", "Text extraction failed"
                    )
                    return False

                logger.info("Text extracted successfully", paper_id=paper_id, text_length=len(text))

                # AI要約生成
                summary = await self.ai_client.generate_summary(text, max_tokens=500)
                if not summary:
                    logger.warning("Failed to generate summary", paper_id=paper_id)
                    await self._update_processing_status(
                        session, paper_id, "summary", "failed", "Summary generation failed"
                    )
                    return False

                # キーワード抽出
                keywords = await self.ai_client.extract_keywords(text, max_keywords=10)

                # 論文情報の更新
                paper.summary = summary
                paper.summary_model = self._get_ai_model_name()
                paper.summary_created_at = datetime.utcnow()
                paper.summary_status = "completed"

                # TODO: キーワードの保存（キーワードテーブルがある場合）

                session.commit()
                await self._update_processing_status(session, paper_id, "summary", "completed")

            logger.info(
                "Paper summarized successfully",
                paper_id=paper_id,
                summary_length=len(summary),
                keywords_count=len(keywords),
            )
            return True

        except Exception as e:
            logger.error("Failed to summarize paper", paper_id=paper_id, error=str(e))

            # エラー状態を記録
            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "summary", "failed", str(e))

            return False

    def _get_ai_model_name(self) -> str:
        """使用中のAIモデル名を取得."""
        if hasattr(self.ai_client, "client") and hasattr(self.ai_client.client, "_api_key"):
            if "openai" in str(type(self.ai_client)):
                return "gpt-4o-mini"
            elif "anthropic" in str(type(self.ai_client)):
                return "claude-3-5-haiku"
        return "unknown"

    async def _update_processing_status(
        self,
        session: Session,
        paper_id: str,
        task_type: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """処理状態を更新."""
        queue_item = (
            session.query(ProcessingQueue).filter_by(paper_id=paper_id, task_type=task_type).first()
        )

        if queue_item:
            queue_item.status = status
            if error_message:
                queue_item.error_message = error_message
                queue_item.retry_count += 1

        # 論文テーブルの状態も更新
        paper = session.query(Paper).filter_by(paper_id=paper_id).first()
        if paper:
            if task_type == "summary":
                paper.summary_status = status

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.pdf_processor.close()
