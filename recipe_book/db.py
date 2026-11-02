from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def _casefold(value):
    return value.casefold() if isinstance(value, str) else value


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        dbapi_connection.create_function("lower", 1, _casefold, deterministic=True)
    finally:
        cursor.close()


class Database:

    def __init__(
        self, url: str = "sqlite:///recipe_book.sqlite3", *, echo: bool = False
    ) -> None:
        self.url = url
        options: dict[str, object] = {}
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False}
            if parsed.database in (None, "", ":memory:"):
                options["poolclass"] = StaticPool

        self.engine = create_engine(url, echo=echo, **options)
        if parsed.get_backend_name() == "sqlite":
            event.listen(self.engine, "connect", _configure_sqlite_connection)

        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()