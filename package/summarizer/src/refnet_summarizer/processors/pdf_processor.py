"""PDF処理モジュール."""

import hashlib
import tempfile

import httpx
import pdfplumber
import PyPDF2
import structlog

logger = structlog.get_logger(__name__)


class PDFProcessor:
    """PDF処理クラス."""

    def __init__(self) -> None:
        """初期化."""
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        )

    async def download_pdf(self, url: str) -> bytes | None:
        """PDFをダウンロード."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            # Content-Typeチェック
            content_type = response.headers.get("content-type", "")
            if "application/pdf" not in content_type:
                logger.warning("Invalid content type", url=url, content_type=content_type)
                return None

            logger.info("PDF downloaded successfully", url=url, size=len(response.content))
            return response.content

        except httpx.HTTPError as e:
            logger.error("Failed to download PDF", url=url, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error downloading PDF", url=url, error=str(e))
            return None

    def extract_text_pypdf2(self, pdf_content: bytes) -> str:
        """PyPDF2でテキスト抽出."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()

                with open(tmp_file.name, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""

                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as e:
                            logger.warning(
                                "Failed to extract text from page", page_num=page_num, error=str(e)
                            )

                    return text.strip()

        except Exception as e:
            logger.error("Failed to extract text with PyPDF2", error=str(e))
            return ""

    def extract_text_pdfplumber(self, pdf_content: bytes) -> str:
        """pdfplumberでテキスト抽出."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()

                with pdfplumber.open(tmp_file.name) as pdf:
                    text = ""

                    for page_num, page in enumerate(pdf.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as e:
                            logger.warning(
                                "Failed to extract text from page", page_num=page_num, error=str(e)
                            )

                    return text.strip()

        except Exception as e:
            logger.error("Failed to extract text with pdfplumber", error=str(e))
            return ""

    def extract_text(self, pdf_content: bytes) -> str:
        """テキスト抽出（複数手法を試行）."""
        # まずpdfplumberを試行
        text = self.extract_text_pdfplumber(pdf_content)

        # 失敗した場合はPyPDF2を試行
        if not text or len(text) < 100:
            logger.info("Fallback to PyPDF2 for text extraction")
            text = self.extract_text_pypdf2(pdf_content)

        # テキストの後処理
        if text:
            text = self._clean_text(text)

        return text

    def _clean_text(self, text: str) -> str:
        """テキストのクリーニング."""
        # 改行の正規化
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 連続する改行を制限
        lines = text.split("\n")
        cleaned_lines = []
        empty_count = 0

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
                empty_count = 0
            else:
                empty_count += 1
                if empty_count <= 1:  # 連続する空行は1つまで
                    cleaned_lines.append("")

        # 連続するスペースを制限
        text = "\n".join(cleaned_lines)
        text = " ".join(text.split())

        return text

    def calculate_hash(self, pdf_content: bytes) -> str:
        """PDFコンテンツのハッシュ計算."""
        return hashlib.sha256(pdf_content).hexdigest()

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.client.aclose()
