"""クローラーサービスのメインエントリーポイント."""

import asyncio
import sys

import structlog

from refnet_crawler.services.crawler_service import CrawlerService

logger = structlog.get_logger(__name__)


async def crawl_paper(paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
    """単一論文のクローリング実行."""
    crawler = CrawlerService()
    try:
        result = await crawler.crawl_paper(paper_id, hop_count, max_hops)
        return result
    finally:
        await crawler.close()


def main() -> None:
    """メイン関数."""
    if len(sys.argv) < 2:
        print("Usage: python -m refnet_crawler.main <paper_id> [hop_count] [max_hops]")
        sys.exit(1)

    paper_id = sys.argv[1]
    hop_count = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    max_hops = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    try:
        result = asyncio.run(crawl_paper(paper_id, hop_count, max_hops))
        if result:
            print(f"Successfully crawled paper: {paper_id}")
        else:
            print(f"Failed to crawl paper: {paper_id}")
            sys.exit(1)
    except Exception as e:
        logger.error("Crawling failed", error=str(e))
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
