"""メインエントリーポイント."""

import sys
import asyncio
from typing import Optional

import structlog

from refnet_summarizer.services.summarizer_service import SummarizerService

logger = structlog.get_logger(__name__)


async def summarize_paper(paper_id: str) -> bool:
    """論文要約の実行."""
    service = SummarizerService()
    try:
        result = await service.summarize_paper(paper_id)
        return result
    finally:
        await service.close()


def main() -> None:
    """CLI エントリーポイント."""
    if len(sys.argv) < 2:
        print("Usage: refnet-summarizer <command> [args...]")
        print("Commands:")
        print("  summarize <paper_id>  - Summarize a paper")
        sys.exit(1)

    command = sys.argv[1]

    if command == "summarize":
        if len(sys.argv) < 3:
            print("Usage: refnet-summarizer summarize <paper_id>")
            sys.exit(1)

        paper_id = sys.argv[2]
        result = asyncio.run(summarize_paper(paper_id))

        if result:
            print(f"Successfully summarized paper: {paper_id}")
            sys.exit(0)
        else:
            print(f"Failed to summarize paper: {paper_id}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
