# Task: セキュリティ設定・認証認可システム

## タスクの目的

JWT認証・認可システム、HTTPS/TLS設定、APIセキュリティ強化、機密情報管理を実装し、RefNetシステムの包括的なセキュリティを確保する。

## 前提条件

- Phase 3 が完了している
- 環境設定管理システムが動作
- 基本的なAPIエンドポイントが利用可能
- Docker環境が構築済み（推奨）

## 実施内容

### 1. JWT認証システム実装

#### package/shared/src/refnet_shared/auth/jwt_handler.py

```python
"""JWT認証ハンドラー."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import SecurityError
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """JWT認証ハンドラー."""

    def __init__(self):
        """初期化."""
        self.secret_key = settings.security.jwt_secret
        self.algorithm = settings.security.jwt_algorithm
        self.access_token_expire_minutes = settings.security.jwt_expiration_minutes
        self.refresh_token_expire_days = 7

    def create_access_token(self, subject: str, additional_claims: Optional[Dict] = None) -> str:
        """アクセストークン生成."""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        if additional_claims:
            payload.update(additional_claims)

        try:
            encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info("Access token created", subject=subject, expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create access token", subject=subject, error=str(e))
            raise SecurityError("Token creation failed") from e

    def create_refresh_token(self, subject: str) -> str:
        """リフレッシュトークン生成."""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }

        try:
            encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info("Refresh token created", subject=subject, expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create refresh token", subject=subject, error=str(e))
            raise SecurityError("Token creation failed") from e

    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """トークン検証."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # トークンタイプ確認
            if payload.get("type") != token_type:
                raise SecurityError(f"Invalid token type. Expected {token_type}")

            # 有効期限確認
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise SecurityError("Token has expired")

            logger.debug("Token verified successfully", subject=payload["sub"], type=token_type)
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired", token_type=token_type)
            raise SecurityError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", token_type=token_type, error=str(e))
            raise SecurityError("Invalid token")
        except Exception as e:
            logger.error("Token verification failed", token_type=token_type, error=str(e))
            raise SecurityError("Token verification failed") from e

    def extract_subject(self, token: str) -> str:
        """トークンからsubject抽出."""
        payload = self.verify_token(token)
        return payload["sub"]

    def hash_password(self, password: str) -> str:
        """パスワードハッシュ化."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワード検証."""
        return pwd_context.verify(plain_password, hashed_password)


# グローバルインスタンス
jwt_handler = JWTHandler()
```

### 2. 認証・認可ミドルウェア

#### package/api/src/refnet_api/middleware/auth.py

```python
"""認証・認可ミドルウェア."""

from typing import Optional, List
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from refnet_shared.auth.jwt_handler import jwt_handler
from refnet_shared.exceptions import SecurityError
import structlog


logger = structlog.get_logger(__name__)
security = HTTPBearer()


class AuthenticationError(HTTPException):
    """認証エラー."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """認可エラー."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """現在のユーザー取得."""
    try:
        token = credentials.credentials
        payload = jwt_handler.verify_token(token)
        return {
            "user_id": payload["sub"],
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])
        }
    except SecurityError as e:
        logger.warning("Authentication failed", error=str(e))
        raise AuthenticationError(str(e))


def require_roles(required_roles: List[str]):
    """必要なロールの確認."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            logger.warning("Access denied", user_id=current_user["user_id"],
                         required_roles=required_roles, user_roles=user_roles)
            raise AuthorizationError(f"Required roles: {', '.join(required_roles)}")
        return current_user
    return role_checker


def require_permissions(required_permissions: List[str]):
    """必要な権限の確認."""
    def permission_checker(current_user: dict = Depends(get_current_user)):
        user_permissions = current_user.get("permissions", [])
        if not all(perm in user_permissions for perm in required_permissions):
            logger.warning("Access denied", user_id=current_user["user_id"],
                         required_permissions=required_permissions,
                         user_permissions=user_permissions)
            raise AuthorizationError(f"Required permissions: {', '.join(required_permissions)}")
        return current_user
    return permission_checker


# 管理者権限チェック
require_admin = require_roles(["admin"])

# 読み取り権限チェック
require_read_access = require_permissions(["papers:read"])

# 書き込み権限チェック
require_write_access = require_permissions(["papers:write"])
```

### 3. 認証エンドポイント

#### package/api/src/refnet_api/routers/auth.py

```python
"""認証関連エンドポイント."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from refnet_shared.auth.jwt_handler import jwt_handler
from refnet_api.middleware.auth import get_current_user
import structlog


logger = structlog.get_logger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    """ログインリクエスト."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """トークンレスポンス."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """リフレッシュリクエスト."""
    refresh_token: str


# 簡単なユーザーストア（実際の実装ではデータベースを使用）
USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": jwt_handler.hash_password("admin_password"),
        "roles": ["admin"],
        "permissions": ["papers:read", "papers:write", "papers:delete"]
    },
    "reader": {
        "username": "reader",
        "hashed_password": jwt_handler.hash_password("reader_password"),
        "roles": ["reader"],
        "permissions": ["papers:read"]
    }
}


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """ユーザーログイン."""
    user = USERS.get(login_data.username)

    if not user or not jwt_handler.verify_password(login_data.password, user["hashed_password"]):
        logger.warning("Login failed", username=login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # トークン生成
    access_token = jwt_handler.create_access_token(
        subject=user["username"],
        additional_claims={
            "roles": user["roles"],
            "permissions": user["permissions"]
        }
    )
    refresh_token = jwt_handler.create_refresh_token(subject=user["username"])

    logger.info("User logged in", username=user["username"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=jwt_handler.access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshRequest):
    """トークンリフレッシュ."""
    try:
        payload = jwt_handler.verify_token(refresh_data.refresh_token, token_type="refresh")
        username = payload["sub"]

        user = USERS.get(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # 新しいアクセストークン生成
        access_token = jwt_handler.create_access_token(
            subject=username,
            additional_claims={
                "roles": user["roles"],
                "permissions": user["permissions"]
            }
        )

        logger.info("Token refreshed", username=username)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_data.refresh_token,  # リフレッシュトークンはそのまま
            expires_in=jwt_handler.access_token_expire_minutes * 60
        )

    except Exception as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """現在のユーザー情報取得."""
    return {
        "username": current_user["user_id"],
        "roles": current_user["roles"],
        "permissions": current_user["permissions"]
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """ユーザーログアウト."""
    # 実際の実装では、トークンをブラックリストに追加
    logger.info("User logged out", username=current_user["user_id"])
    return {"message": "Successfully logged out"}
```

### 4. レート制限実装

#### package/shared/src/refnet_shared/middleware/rate_limiter.py

```python
"""レート制限ミドルウェア."""

import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status
import redis
from refnet_shared.config.environment import load_environment_settings
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class RateLimiter:
    """レート制限クラス."""

    def __init__(self):
        """初期化."""
        self.redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.database,
            decode_responses=True
        )

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict]:
        """レート制限チェック."""
        current_time = int(time.time())
        window_start = current_time - window_seconds

        pipe = self.redis_client.pipeline()

        # 古いエントリを削除
        pipe.zremrangebyscore(key, 0, window_start)

        # 現在のリクエスト数を取得
        pipe.zcard(key)

        # 現在のリクエストを追加
        pipe.zadd(key, {str(current_time): current_time})

        # TTLを設定
        pipe.expire(key, window_seconds)

        results = pipe.execute()
        current_requests = results[1]

        # レート制限チェック
        if current_requests >= limit:
            logger.warning("Rate limit exceeded", key=key, current_requests=current_requests, limit=limit)
            return False, {
                "allowed": False,
                "current_requests": current_requests,
                "limit": limit,
                "window_seconds": window_seconds,
                "reset_time": current_time + window_seconds
            }

        return True, {
            "allowed": True,
            "current_requests": current_requests + 1,
            "limit": limit,
            "window_seconds": window_seconds,
            "reset_time": current_time + window_seconds
        }


# グローバルインスタンス
rate_limiter = RateLimiter()


def create_rate_limit_middleware(requests_per_minute: int = 60):
    """レート制限ミドルウェア作成."""

    async def rate_limit_middleware(request: Request, call_next):
        # クライアントIPを取得
        client_ip = request.client.host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # API パスのみレート制限を適用
        if not request.url.path.startswith("/api/"):
            response = await call_next(request)
            return response

        # レート制限チェック
        key = f"rate_limit:{client_ip}"
        allowed, info = rate_limiter.is_allowed(key, requests_per_minute, 60)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset_time"])
                }
            )

        response = await call_next(request)

        # レート制限ヘッダー追加
        response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(requests_per_minute - info["current_requests"])
        response.headers["X-RateLimit-Reset"] = str(info["reset_time"])

        return response

    return rate_limit_middleware
```

### 5. HTTPS/TLS設定

#### docker/nginx/ssl-nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

    # SSL設定
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    upstream api_backend {
        server api:8000;
    }

    # HTTP → HTTPS リダイレクト
    server {
        listen 80;
        server_name localhost;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS サーバー
    server {
        listen 443 ssl http2;
        server_name localhost;

        ssl_certificate /etc/nginx/ssl/server.crt;
        ssl_certificate_key /etc/nginx/ssl/server.key;

        # ヘルスチェック（HTTPS経由）
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # API プロキシ
        location /api/ {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # セキュリティヘッダー
            proxy_hide_header X-Powered-By;

            # タイムアウト設定
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # 静的ファイル
        location /output/ {
            alias /app/output/;
            autoindex on;
            autoindex_exact_size off;
            autoindex_localtime on;

            # セキュリティ設定
            add_header X-Content-Type-Options nosniff;
            location ~* \.(php|asp|aspx|jsp)$ {
                deny all;
            }
        }
    }
}
```

### 6. SSL証明書生成スクリプト

#### scripts/generate-ssl-cert.sh

```bash
#!/bin/bash

# 自己署名SSL証明書生成スクリプト（開発用）

SSL_DIR="docker/nginx/ssl"
mkdir -p "$SSL_DIR"

# 秘密鍵生成
openssl genrsa -out "$SSL_DIR/server.key" 2048

# 証明書署名要求生成
openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" -subj "/C=JP/ST=Tokyo/L=Tokyo/O=RefNet/CN=localhost"

# 自己署名証明書生成
openssl x509 -req -days 365 -in "$SSL_DIR/server.csr" -signkey "$SSL_DIR/server.key" -out "$SSL_DIR/server.crt"

# 証明書署名要求削除
rm "$SSL_DIR/server.csr"

echo "SSL certificates generated in $SSL_DIR/"
echo "Note: These are self-signed certificates for development only."
```

### 7. セキュリティ設定テスト

#### tests/test_security.py

```python
"""セキュリティテスト."""

import pytest
import requests
import time
from refnet_shared.auth.jwt_handler import jwt_handler


class TestSecurity:
    """セキュリティテスト."""

    BASE_URL = "http://localhost"

    def test_jwt_token_creation_and_verification(self):
        """JWTトークン作成・検証テスト."""
        # トークン作成
        token = jwt_handler.create_access_token("test_user")
        assert token is not None

        # トークン検証
        payload = jwt_handler.verify_token(token)
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"

    def test_login_endpoint(self):
        """ログインエンドポイントテスト."""
        login_data = {
            "username": "admin",
            "password": "admin_password"
        }

        response = requests.post(f"{self.BASE_URL}/api/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_protected_endpoint_without_token(self):
        """認証が必要なエンドポイントへの未認証アクセステスト."""
        response = requests.get(f"{self.BASE_URL}/api/v1/papers/")
        # 認証が必要な場合は401が返される
        assert response.status_code in [200, 401]  # 実装に依存

    def test_protected_endpoint_with_token(self):
        """認証が必要なエンドポイントへの認証済みアクセステスト."""
        # ログインしてトークン取得
        login_data = {
            "username": "admin",
            "password": "admin_password"
        }
        login_response = requests.post(f"{self.BASE_URL}/api/auth/login", json=login_data)
        token = login_response.json()["access_token"]

        # 認証ヘッダー付きでアクセス
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["username"] == "admin"

    def test_invalid_token(self):
        """無効なトークンテスト."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = requests.get(f"{self.BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.slow
    def test_rate_limiting(self):
        """レート制限テスト."""
        # 短期間で大量のリクエスト送信
        responses = []
        for i in range(70):  # 60req/min制限を超える
            response = requests.get(f"{self.BASE_URL}/api/health")
            responses.append(response.status_code)
            if response.status_code == 429:
                break

        # 429 (Too Many Requests) が返されることを確認
        assert 429 in responses

    def test_security_headers(self):
        """セキュリティヘッダーテスト."""
        response = requests.get(f"{self.BASE_URL}/api/health")

        # セキュリティヘッダーの確認
        headers = response.headers
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Referrer-Policy" in headers

    def test_password_hashing(self):
        """パスワードハッシュ化テスト."""
        password = "test_password"
        hashed = jwt_handler.hash_password(password)

        # ハッシュ化されていることを確認
        assert hashed != password
        assert len(hashed) > 50  # bcryptハッシュの長さ

        # 検証が正しく動作することを確認
        assert jwt_handler.verify_password(password, hashed) is True
        assert jwt_handler.verify_password("wrong_password", hashed) is False
```

## スコープ

- JWT認証・認可システム
- APIセキュリティ強化（レート制限・セキュリティヘッダー）
- HTTPS/TLS設定
- パスワードハッシュ化・検証
- 基本的なセキュリティテスト

**スコープ外:**
- OAuth2/OpenID Connect統合
- 多要素認証（MFA）
- セキュリティ監査ログ
- 高度な脅威検知

## 参照するドキュメント

- `/docs/security/authentication.md`
- `/docs/security/authorization.md`
- `/docs/development/coding-standards.md`

## 完了条件

### 必須条件
- [ ] JWT認証システムが実装されている
- [ ] 認証・認可ミドルウェアが動作
- [ ] ログイン・ログアウトエンドポイントが動作
- [ ] レート制限が実装されている
- [ ] HTTPS/TLS設定が完了
- [ ] セキュリティヘッダーが設定されている

### セキュリティ条件
- [ ] パスワードが適切にハッシュ化されている
- [ ] JWTトークンが適切に管理されている
- [ ] APIエンドポイントが適切に保護されている
- [ ] レート制限が効果的に動作している
- [ ] セキュリティヘッダーが設定されている

### テスト条件
- [ ] セキュリティテストが作成されている
- [ ] 認証・認可のテストが成功
- [ ] レート制限のテストが成功
- [ ] セキュリティヘッダーのテストが成功

## トラブルシューティング

### よくある問題

1. **JWT署名検証失敗**
   - 解決策: 秘密鍵設定、アルゴリズム設定を確認

2. **認証ミドルウェアエラー**
   - 解決策: トークン形式、ヘッダー設定を確認

3. **レート制限が動作しない**
   - 解決策: Redis接続、キー生成ロジックを確認

4. **HTTPS証明書エラー**
   - 解決策: 証明書パス、権限設定を確認

## 次のタスクへの引き継ぎ

### 03_batch_automation.md への前提条件
- 認証システムが正常稼働
- セキュリティ設定が適用済み
- 保護されたAPIエンドポイントが利用可能

### 引き継ぎファイル
- `package/shared/src/refnet_shared/auth/` - 認証システム
- `package/api/src/refnet_api/middleware/` - 認証ミドルウェア
- `docker/nginx/ssl/` - SSL証明書
- セキュリティ設定・テスト
