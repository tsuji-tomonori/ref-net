"""認証関連エンドポイント."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from refnet_shared.auth.jwt_handler import jwt_handler

from refnet_api.middleware.auth import get_current_user

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
async def login(login_data: LoginRequest) -> TokenResponse:
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
async def refresh_token(refresh_data: RefreshRequest) -> TokenResponse:
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
        ) from e


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)) -> dict:
    """現在のユーザー情報取得."""
    return {
        "username": current_user["user_id"],
        "roles": current_user["roles"],
        "permissions": current_user["permissions"]
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)) -> dict:
    """ユーザーログアウト."""
    # 実際の実装では、トークンをブラックリストに追加
    logger.info("User logged out", username=current_user["user_id"])
    return {"message": "Successfully logged out"}
