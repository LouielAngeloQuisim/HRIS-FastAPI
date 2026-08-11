from sqlmodel import Session, create_engine, select

from app.config.settings import settings

# Importing the model registry has the side effect of registering every table
# on SQLModel.metadata. Alembic autogenerate and create_all both depend on it,
# so it must happen before the engine is used.
import app.models  # noqa: F401
from app.user.models import User, UserCreate

# Exposed as a module constant so configuration intent is assertable without
# reaching into SQLAlchemy's pool internals.
ENGINE_CONNECT_ARGS: dict[str, object] = {
    "connect_timeout": settings.POSTGRES_CONNECT_TIMEOUT_SECONDS,
}

engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=settings.SQLALCHEMY_ECHO,
    pool_pre_ping=True,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_recycle=settings.POSTGRES_POOL_RECYCLE_SECONDS,
    connect_args=ENGINE_CONNECT_ARGS,
)


def init_db(session: Session) -> None:
    """Seed the baseline data every environment needs.

    Ordering matters: RBAC reference data must exist before the first
    superuser is created, so the superuser can be bound to a real role rather
    than depending solely on the is_superuser bypass.
    """
    from app.rbac.seed import SUPER_ADMIN_ROLE_CODE, seed_rbac
    from app.rbac.selectors import get_role_by_code

    seed_rbac(session=session)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        from app.user.services import create_user

        user = create_user(session=session, user_create=user_in)

    if user.role_id is None:
        super_admin = get_role_by_code(session=session, code=SUPER_ADMIN_ROLE_CODE)
        if super_admin is not None:
            user.role_id = super_admin.id
            session.add(user)
            session.commit()
            session.refresh(user)
