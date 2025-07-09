"""JWT認証ハンドラー."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import structlog
from passlib.context import CryptContext

from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import SecurityError

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """JWT認証ハンドラー."""

    def __init__(self) -> None:
        """初期化."""
        self.secret_key = settings.security.jwt_secret
        self.algorithm = settings.security.jwt_algorithm
        self.access_token_expire_minutes = settings.security.jwt_expiration_minutes
        self.refresh_token_expire_days = 7

    def create_access_token(self, subject: str, additional_claims: dict | None = None) -> str:
        """アクセストークン生成."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
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
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }

        try:
            encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info("Refresh token created", subject=subject, expires_at=expire)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create refresh token", subject=subject, error=str(e))
            raise SecurityError("Token creation failed") from e

    def verify_token(self, token: str, token_type: str = "access") -> dict[str, Any]:
        """トークン検証."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # トークンタイプ確認
            if payload.get("type") != token_type:
                raise SecurityError(f"Invalid token type. Expected {token_type}")

            # 有効期限確認
            if datetime.now(timezone.utc) > datetime.fromtimestamp(payload["exp"], tz=timezone.utc):
                raise SecurityError("Token has expired")

            logger.debug("Token verified successfully", subject=payload["sub"], type=token_type)
            return payload  # type: ignore

        except SecurityError:
            # Re-raise SecurityError without wrapping
            raise
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired", token_type=token_type)
            raise SecurityError("Token has expired") from None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", token_type=token_type, error=str(e))
            raise SecurityError("Invalid token") from e
        except Exception as e:
            logger.error("Token verification failed", token_type=token_type, error=str(e))
            raise SecurityError("Token verification failed") from e

    def extract_subject(self, token: str) -> str:
        """トークンからsubject抽出."""
        payload = self.verify_token(token)
        return str(payload["sub"])

    def hash_password(self, password: str) -> str:
        """パスワードハッシュ化."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワード検証."""
        return pwd_context.verify(plain_password, hashed_password)


# グローバルインスタンス
jwt_handler = JWTHandler()
