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

## 環境設定

### 環境ファイルの作成

```bash
# 開発環境用設定ファイル作成
refnet-shared env create development

# ステージング環境用設定ファイル作成
refnet-shared env create staging

# 本番環境用設定ファイル作成
refnet-shared env create production
```

### 設定検証

```bash
# 現在の環境設定を検証
refnet-shared env validate

# 特定環境の必須変数チェック
refnet-shared env check production
```

### 設定エクスポート

```bash
# 設定をJSONでエクスポート（機密情報除く）
refnet-shared env export --output config.json
```

### 環境切り替え

```bash
# 環境変数で指定
export NODE_ENV=production

# または.envファイルで指定
echo "NODE_ENV=production" > .env
```

### 環境別設定ファイル

プロジェクトでは以下の環境設定ファイルを使用します：

- `.env.example` - 設定テンプレート（リポジトリに含む）
- `.env.development` - 開発環境設定
- `.env.staging` - ステージング環境設定
- `.env.production` - 本番環境設定
- `.env` - ローカル設定（gitignore対象）

### 環境設定の使用方法

```python
from refnet_shared.config.environment import load_environment_settings

# 環境設定の読み込み
settings = load_environment_settings()

# 環境判定
if settings.is_production():
    # 本番環境での処理
    pass
elif settings.is_development():
    # 開発環境での処理
    pass
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
