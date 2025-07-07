FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen

# アプリケーションコピー
COPY src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src

# ポート
EXPOSE 8000

# 起動コマンド
CMD ["uvicorn", "refnet_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
