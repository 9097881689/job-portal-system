from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.db.session import Base, engine
from app.models import job  # noqa: F401 - imports models so SQLAlchemy can create tables.
from sqlalchemy import inspect, text


def ensure_sqlite_columns() -> None:
    """Add new columns for existing SQLite installs without requiring Alembic."""

    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("processed_jobs")}
    published_existing = {column["name"] for column in inspector.get_columns("published_posts")}

    processed_columns = {
        "canonical_key": "ALTER TABLE processed_jobs ADD COLUMN canonical_key VARCHAR(64) DEFAULT ''",
        "content_hash": "ALTER TABLE processed_jobs ADD COLUMN content_hash VARCHAR(64) DEFAULT ''",
        "source_priority": "ALTER TABLE processed_jobs ADD COLUMN source_priority INTEGER DEFAULT 100",
        "blogger_url": "ALTER TABLE processed_jobs ADD COLUMN blogger_url TEXT",
    }
    published_columns = {
        "content_hash": "ALTER TABLE published_posts ADD COLUMN content_hash VARCHAR(64)",
        "source_url": "ALTER TABLE published_posts ADD COLUMN source_url TEXT",
    }

    with engine.begin() as conn:
        for name, sql in processed_columns.items():
            if name not in existing:
                conn.execute(text(sql))
        for name, sql in published_columns.items():
            if name not in published_existing:
                conn.execute(text(sql))


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()
    print("Database tables created.")
