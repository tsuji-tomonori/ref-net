# Task: セキュリティ設定追加改善 (PR #32 レビュー対応)

## タスクの目的

PR #32のセキュリティレビューで特定された⚠️項目への対応を実施する。

## 前提条件

- PR #32がマージ済み
- JWT認証システムが実装済み (`jwt_handler.py` 存在確認済み)
- Flower UI認証、レート制限、監査ログが実装済み
- TLS/HTTPS設定が完了済み

## 実施内容

### 1. レート制限でのJWTトークン検証実装

#### package/shared/src/refnet_shared/middleware/rate_limiter.py の修正

```python
# 156-166行目のTODOコメント部分を以下に置換

            # JWT トークンからユーザーIDを取得する処理
            try:
                from refnet_shared.auth.jwt_handler import jwt_handler
                token = auth_header.split(" ")[1]
                payload = jwt_handler.verify_token(token)
                user_id = payload.get("sub")
                logger.debug("JWT token verified for rate limiting", user_id=user_id)
            except ImportError:
                logger.warning("JWT handler not available, falling back to IP-based rate limiting")
                pass
            except Exception as e:
                logger.debug("JWT token verification failed", error=str(e))
                # 認証失敗でもレート制限は継続（IPベース）
                pass
```

### 2. Flowerセッション管理の明示的設定

#### package/shared/Dockerfile.flower の修正

```dockerfile
# 32行目のENTRYPOINTを以下に修正
ENTRYPOINT ["sh", "-c", "celery -A refnet_shared.celery_app flower --port=5555 --basic_auth=${FLOWER_USER}:${FLOWER_PASSWORD} --url-prefix=${FLOWER_URL_PREFIX:-/flower} --session-timeout=30m --max-workers=100"]
```

### 3. APIエンドポイント認証の強化

#### package/api/src/refnet_api/routers/papers.py の修正

```python
# ファイル上部のimportに追加
from refnet_api.middleware.auth import get_current_user

# @router.get("/", response_model=PaperListResponse) を以下に修正
@router.get("/", response_model=PaperListResponse)
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 認証必須化
) -> PaperListResponse:
    """論文一覧取得（認証必須）."""
    logger.info("Papers list requested", user_id=current_user["user_id"], skip=skip, limit=limit)
    # 既存の実装を維持
```

#### その他の保護すべきエンドポイント

```python
# POST /papers/ - 論文作成
@router.post("/", response_model=PaperCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_paper(
    paper: PaperCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 追加
):

# PUT /papers/{paper_id} - 論文更新
@router.put("/{paper_id}", response_model=APIPaperResponse)
async def update_paper(
    paper_id: str,
    paper: PaperUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 追加
):
```

### 4. 認証テストケースの追加

#### package/api/tests/test_auth_integration.py (新規作成)

```python
"""認証統合テスト."""

import pytest
from fastapi.testclient import TestClient
from refnet_shared.auth.jwt_handler import jwt_handler

def test_papers_endpoint_without_auth(client: TestClient):
    """認証なしでの論文一覧アクセステスト."""
    response = client.get("/api/v1/papers/")
    assert response.status_code == 401

def test_papers_endpoint_with_valid_token(client: TestClient):
    """有効なトークンでの論文一覧アクセステスト."""
    # テスト用トークン生成
    token = jwt_handler.create_access_token("test_user")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/papers/", headers=headers)
    assert response.status_code == 200

def test_papers_endpoint_with_invalid_token(client: TestClient):
    """無効なトークンでの論文一覧アクセステスト."""
    headers = {"Authorization": "Bearer invalid_token"}

    response = client.get("/api/v1/papers/", headers=headers)
    assert response.status_code == 401
```

## 完了条件

### 必須条件
- [ ] rate_limiter.pyでJWTトークン検証が動作している
- [ ] Flowerのセッションタイムアウトが30分に設定されている
- [ ] papers.pyの主要エンドポイントで認証が必須となっている
- [ ] 認証統合テストが作成・合格している
- [ ] `moon :check`が全パッケージで成功している

### セキュリティ確認
- [ ] 未認証でのAPIアクセスが適切に拒否される
- [ ] レート制限でユーザー別制御が動作している
- [ ] Flowerで30分後に自動ログアウトされる
- [ ] 監査ログに認証イベントが記録される

### テスト確認
- [ ] `pytest package/api/tests/test_auth_integration.py -v` が成功
- [ ] Bearer認証でのレート制限ユーザー別制御テスト成功
- [ ] API認証のエンドツーエンドテスト成功

## 推定作業時間

**3-5時間**
- rate_limiter修正：30分
- Flower設定：30分
- papers.py認証追加：1-2時間
- テストケース作成：1-2時間
- 動作確認・デバッグ：1時間

## 優先度

**🚨 高優先度** - セキュリティの中核機能のため即座対応

## 依存関係

- JWT認証システム（既存）
- レート制限システム（既存）
- Flower UI（既存）
- APIエンドポイント（既存）

## 注意点

- 既存のAPIクライアントがある場合、認証が必須になることでBreaking Changeとなる
- 段階的適用（一部エンドポイントから開始）も検討可能
- テスト環境での動作確認を必ず実施すること
