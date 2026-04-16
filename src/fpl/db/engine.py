from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from fpl.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        from sqlalchemy import event as sa_event

        settings = get_settings()
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            echo=False,
            connect_args={"timeout": 30},
        )

        # Enable WAL mode for concurrent read/write support
        @sa_event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(
            dbapi_conn: object, _rec: object
        ) -> None:
            cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from sqlalchemy import text

    from fpl.db.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Lightweight column migrations for existing SQLite DBs
    migrations = [
        (
            "fixtures",
            "finished_provisional",
            "ALTER TABLE fixtures ADD COLUMN finished_provisional "
            "BOOLEAN DEFAULT 0",
        ),
        (
            "my_team_players",
            "user_id",
            "ALTER TABLE my_team_players ADD COLUMN user_id "
            "INTEGER DEFAULT 1",
        ),
        (
            "my_account",
            "user_id",
            "ALTER TABLE my_account ADD COLUMN user_id "
            "INTEGER DEFAULT 1",
        ),
    ]
    with engine.begin() as conn:
        for table, column, ddl in migrations:
            rows = conn.execute(
                text(f"PRAGMA table_info({table})")
            ).fetchall()
            cols = {r[1] for r in rows}
            if column not in cols:
                conn.execute(text(ddl))
