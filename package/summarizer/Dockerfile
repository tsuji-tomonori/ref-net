FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY summarizer/pyproject.toml summarizer/uv.lock summarizer/README.md ./
# shared パッケージをコピー（uv.sources で参照されているため）
COPY shared/ ../shared/
RUN pip install uv
RUN uv sync --frozen

# アプリケーションコピー
COPY summarizer/src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src

# 起動コマンド
CMD ["celery", "-A", "refnet_summarizer.tasks.celery_app", "worker", "--loglevel=info", "--queue=summarize"]
