# RefNet Shared Library

RefNet論文関係性可視化システムの共通ライブラリです。

## 機能

- 設定管理（Pydantic Settings）
- ロギング設定（structlog）
- 共通例外クラス
- ユーティリティ関数

## インストール

```bash
uv sync
```

## 使用方法

### 設定

```python
from refnet_shared.config import settings

# データベースURL取得
db_url = settings.database.url

# Redis URL取得
redis_url = settings.redis.url
```

### ロギング

```python
from refnet_shared.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
logger.info("Hello, world!")
```

### CLI

```bash
# アプリケーション情報表示
refnet-shared info

# 設定検証
refnet-shared validate

# バージョン表示
refnet-shared version
```

## 開発

```bash
# テスト実行
moon run shared:test

# リント実行
moon run shared:lint

# 型チェック
moon run shared:typecheck

# 全チェック実行
moon run shared:check
```
