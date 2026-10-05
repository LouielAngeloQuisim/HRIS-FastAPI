"""Seed a regular user only in an explicitly isolated local E2E environment."""

import os

from sqlmodel import Session

from app.config.database import engine, init_db
from app.config.settings import settings
from app.user.models import UserCreate
from app.user.selectors import get_user_by_email
from app.user.services import create_user


def main():
    if (
        os.environ.get("E2E_SEED_ALLOWED") != "true"
        or settings.ENVIRONMENT != "local"
        or settings.POSTGRES_SERVER not in ("localhost", "127.0.0.1")
    ):
        raise SystemExit("E2E seeding requires explicit opt-in and a local database")
    try:
        with Session(engine) as session:
            init_db(session)
            email = os.environ.get("E2E_USER_EMAIL", "user@example.com")
            password = os.environ.get("E2E_USER_PASSWORD", "e2e-user-placeholder")
            if get_user_by_email(session=session, email=email) is None:
                create_user(
                    session=session,
                    user_create=UserCreate(
                        email=email, password=password, is_superuser=False
                    ),
                )
    except Exception as exc:
        raise RuntimeError(
            f"E2E user seed failed; dependent browser tests were not started: {exc}"
        ) from exc


if __name__ == "__main__":
    main()
