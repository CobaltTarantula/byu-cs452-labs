## This script is used to drop the tables in the database

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

CONNECTION = os.getenv("DATABASE_URL")

DROP_TABLE = "DROP TABLE IF EXISTS podcast_segment, podcast CASCADE"


def main() -> None:
    if not CONNECTION:
        raise SystemExit("Set DATABASE_URL in your environment or .env file first.")
    with psycopg2.connect(CONNECTION) as conn, conn.cursor() as cursor:
        cursor.execute(DROP_TABLE)


if __name__ == "__main__":
    main()
