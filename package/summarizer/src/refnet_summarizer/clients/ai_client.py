"""AI APIクライアント."""

from abc import ABC, abstractmethod
from typing import Optional
import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import ExternalAPIError
import structlog


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

    def __init__(self, api_key: Optional[str] = None) -> None:
        """初期化."""
        self.client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key
        )

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
                        "content": "あなたは論文要約の専門家です。以下の論文テキストを読んで、研究内容、手法、結果、意義を含む簡潔で有用な要約を作成してください。要約は日本語で記述し、専門用語は適切に説明してください。"
                    },
                    {
                        "role": "user",
                        "content": f"以下の論文テキストを要約してください（最大{max_tokens}トークン）:\n\n{text[:8000]}"  # APIの制限を考慮
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )

            summary = response.choices[0].message.content
            if not summary:
                raise ExternalAPIError("Empty response from OpenAI")

            logger.info("Summary generated successfully", model="gpt-4o-mini", tokens=len(summary.split()))
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
                        "content": f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。技術用語、手法名、概念名を優先し、カンマ区切りで返してください。"
                    },
                    {
                        "role": "user",
                        "content": text[:4000]  # APIの制限を考慮
                    }
                ],
                max_tokens=200,
                temperature=0.1,
            )

            keywords_text = response.choices[0].message.content
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(',')]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with OpenAI", error=str(e))
            return []


class AnthropicClient(AIClient):
    """Anthropic APIクライアント."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        """初期化."""
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )

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
                        "content": f"以下の論文テキストを読んで、研究内容、手法、結果、意義を含む簡潔で有用な要約を日本語で作成してください:\n\n{text[:100000]}"
                    }
                ]
            )

            summary = response.content[0].text
            if not summary:
                raise ExternalAPIError("Empty response from Anthropic")

            logger.info("Summary generated successfully", model="claude-3-5-haiku", tokens=len(summary.split()))
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
                        "content": f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。技術用語、手法名、概念名を優先し、カンマ区切りで返してください:\n\n{text[:50000]}"
                    }
                ]
            )

            keywords_text = response.content[0].text
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(',')]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with Anthropic", error=str(e))
            return []


def create_ai_client() -> AIClient:
    """AI クライアントの作成."""
    if settings.openai_api_key:
        return OpenAIClient()
    elif settings.anthropic_api_key:
        return AnthropicClient()
    else:
        raise ExternalAPIError("No AI API key configured")
