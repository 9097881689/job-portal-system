from __future__ import annotations

import argparse
import logging

from app.core.logging import configure_logging
from app.db.session import Base, SessionLocal, engine
from app.models import job  # noqa: F401 - imports models for metadata creation.
from app.services.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Blogger Job Portal")
    parser.add_argument("--dry-run", action="store_true", help="Generate content without publishing to Blogger.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum jobs to process in this run.")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        stats = run_pipeline(db, dry_run=args.dry_run, limit=args.limit)

    logging.getLogger(__name__).info("Run completed: %s", stats)
    print(stats)


if __name__ == "__main__":
    main()
