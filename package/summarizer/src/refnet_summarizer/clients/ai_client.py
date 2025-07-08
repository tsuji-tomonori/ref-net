"""AI APIクライアント."""

import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import openai
import structlog
from refnet_shared.config.environment import load_environment_settings  # type: ignore[import-untyped]
from refnet_shared.exceptions import ExternalAPIError  # type: ignore[import-untyped]
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class AIClient(ABC):
    """AI APIクライアントの基底クラス."""

    @abstractmethod
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        pass

    @abstractmethod
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        pass


class OpenAIClient(AIClient):
    """OpenAI APIクライアント."""

    def __init__(self, api_key: str | None = None) -> None:
        """初期化."""
        self.client = openai.AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたは論文要約の専門家です。以下の論文テキストを読んで、"
                            "研究内容、手法、結果、意義を含む簡潔で有用な要約を作成してください。"
                            "要約は日本語で記述し、専門用語は適切に説明してください。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"以下の論文テキストを要約してください"
                            f"（最大{max_tokens}トークン）:\n\n{text[:8000]}"
                        ),  # APIの制限を考慮
                    },
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )

            summary = response.choices[0].message.content
            if not summary:
                raise ExternalAPIError("Empty response from OpenAI")

            logger.info(
                "Summary generated successfully",
                model="gpt-4o-mini",
                tokens=len(summary.split()),
            )
            return summary.strip()

        except openai.RateLimitError as e:
            logger.warning("OpenAI rate limit exceeded")
            raise ExternalAPIError("Rate limit exceeded") from e
        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise ExternalAPIError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error with OpenAI", error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。"
                            "技術用語、手法名、概念名を優先し、カンマ区切りで返してください。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": text[:4000],  # APIの制限を考慮
                    },
                ],
                max_tokens=200,
                temperature=0.1,
            )

            keywords_text = response.choices[0].message.content
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(",")]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with OpenAI", error=str(e))
            return []


class AnthropicClient(AIClient):
    """Anthropic APIクライアント."""

    def __init__(self, api_key: str | None = None) -> None:
        """初期化."""
        self.client = anthropic.AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=max_tokens,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "以下の論文テキストを読んで、研究内容、手法、結果、意義を含む"
                            f"簡潔で有用な要約を日本語で作成してください:\n\n{text[:100000]}"
                        ),
                    }
                ],
            )

            # Anthropicのレスポンスから適切にテキストを取得
            content_block = response.content[0]
            if hasattr(content_block, 'text'):
                summary = content_block.text
            else:
                raise ExternalAPIError("Invalid response format from Anthropic")
            if not summary:
                raise ExternalAPIError("Empty response from Anthropic")

            logger.info(
                "Summary generated successfully",
                model="claude-3-5-haiku",
                tokens=len(summary.split()),
            )
            return summary.strip()

        except anthropic.RateLimitError as e:
            logger.warning("Anthropic rate limit exceeded")
            raise ExternalAPIError("Rate limit exceeded") from e
        except anthropic.APIError as e:
            logger.error("Anthropic API error", error=str(e))
            raise ExternalAPIError(f"Anthropic API error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error with Anthropic", error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。"
                            f"技術用語、手法名、概念名を優先し、カンマ区切りで返してください:\n\n{text[:50000]}"
                        ),
                    }
                ],
            )

            # Anthropicのレスポンスから適切にテキストを取得
            content_block = response.content[0]
            if hasattr(content_block, 'text'):
                keywords_text = content_block.text
            else:
                keywords_text = ""
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(",")]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with Anthropic", error=str(e))
            return []


class ClaudeCodeClient(AIClient):
    """Claude Code CLIクライアント."""

    def __init__(self, claude_command: str = "claude") -> None:
        """初期化."""
        self.claude_command = claude_command
        self._check_claude_availability()

    def _check_claude_availability(self) -> None:
        """Claude Codeの利用可能性チェック."""
        try:
            result = subprocess.run(
                [self.claude_command, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise ExternalAPIError("Claude Code CLI not available")
            logger.info("Claude Code CLI detected", version=result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise ExternalAPIError(f"Claude Code CLI not found: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成（Claude Code使用）."""
        try:
            # 一時ファイルに論文テキストを保存
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)

            try:
                # Claude Codeを使用して要約生成
                prompt = (
                    f"この論文テキストファイル({tmp_path.name})を読んで、"
                    f"研究内容、手法、結果、意義を含む簡潔で有用な要約を"
                    f"日本語で{max_tokens}文字以内で作成してください。"
                )

                result = subprocess.run(
                    [self.claude_command, "-p", prompt, str(tmp_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2分のタイムアウト
                )

                if result.returncode != 0:
                    error_msg = result.stderr or "Unknown error"
                    raise ExternalAPIError(f"Claude Code execution failed: {error_msg}")

                summary = result.stdout.strip()
                if not summary:
                    raise ExternalAPIError("Empty response from Claude Code")

                logger.info(
                    "Summary generated successfully",
                    model="claude-code",
                    length=len(summary),
                )
                return summary

            finally:
                # 一時ファイルを削除
                tmp_path.unlink(missing_ok=True)

        except subprocess.TimeoutExpired as e:
            logger.error("Claude Code timeout", error=str(e))
            raise ExternalAPIError("Claude Code request timeout") from e
        except Exception as e:
            logger.error("Unexpected error with Claude Code", error=str(e))
            raise ExternalAPIError(f"Claude Code error: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出（Claude Code使用）."""
        try:
            # 一時ファイルに論文テキストを保存
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)

            try:
                prompt = (
                    f"この論文テキストファイル({tmp_path.name})から"
                    f"重要なキーワードを{max_keywords}個抽出してください。"
                    f"技術用語、手法名、概念名を優先し、カンマ区切りで返してください。"
                )

                result = subprocess.run(
                    [self.claude_command, "-p", prompt, str(tmp_path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    logger.warning("Claude Code keyword extraction failed", error=result.stderr)
                    return []

                keywords_text = result.stdout.strip()
                if not keywords_text:
                    return []

                keywords = [kw.strip() for kw in keywords_text.split(",")]
                keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

                logger.info("Keywords extracted successfully", count=len(keywords))
                return keywords

            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error("Failed to extract keywords with Claude Code", error=str(e))
            return []


def create_ai_client() -> AIClient:
    """AI クライアントの作成."""
    # 環境変数での優先順位設定
    ai_provider = getattr(settings, "ai_provider", "auto").lower()

    if ai_provider == "claude-code":
        return ClaudeCodeClient()
    elif ai_provider == "openai" and settings.openai_api_key:
        return OpenAIClient()
    elif ai_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicClient()
    elif ai_provider == "auto":
        # 自動選択: Claude Code > OpenAI > Anthropic
        try:
            return ClaudeCodeClient()
        except ExternalAPIError:
            if settings.openai_api_key:
                return OpenAIClient()
            elif settings.anthropic_api_key:
                return AnthropicClient()

    raise ExternalAPIError("No AI service configured or available")
