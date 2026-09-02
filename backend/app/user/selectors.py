import uuid

from sqlmodel import Session, col, func, select

from app.user.models import User


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_users(*, session: Session, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return list(users), count
