from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionDep
from app.api.schemas import LoginRequest, TokenResponse
from app.application.security import create_access_token, verify_password
from app.infrastructure.persistence.models import User

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = session.query(User).filter(User.email == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(user.id))
