"""Build, load, query, and report using Docker's URL or embedded pgserver."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    if not os.getenv("DATABASE_URL"):
        try:
            import pgserver
        except ImportError as exc:
            raise SystemExit(
                "Set DATABASE_URL or install pgserver for the embedded PostgreSQL option."
            ) from exc
        pg_data = Path(os.getenv("PGDATA_DIR", ".pgdata")).resolve()
        server = pgserver.get_server(str(pg_data))
        os.environ["DATABASE_URL"] = server.get_uri()
        print("Started embedded PostgreSQL with pgvector.", flush=True)

    from recommender.db_build import main as build_database
    from recommender.db_insert import main as load_data
    from recommender.db_query import main as run_queries
    from create_report import create_pdf

    build_database()
    print("Starting data load.", flush=True)
    load_data()
    print("Running recommendation queries.", flush=True)
    run_queries()
    print(f"Wrote {create_pdf()}")


if __name__ == "__main__":
    main()
