from fastapi import APIRouter
from typing import Any
from pydantic import BaseModel

from app.user.schemas import UserPublic
from app.common.dependencies import SessionDep
from app.common.security import get_password_hash
from app.user.models import User

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    return user