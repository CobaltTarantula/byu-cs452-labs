"""Create the podcast recommender schema in PostgreSQL with pgvector."""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

CONNECTION = os.getenv("DATABASE_URL")

CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector"
CREATE_PODCAST_TABLE = """
CREATE TABLE IF NOT EXISTS podcast (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL
)
"""
CREATE_SEGMENT_TABLE = """
CREATE TABLE IF NOT EXISTS podcast_segment (
    id TEXT PRIMARY KEY,
    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(128) NOT NULL,
    podcast_id TEXT NOT NULL REFERENCES podcast(id)
)
"""


def main() -> None:
    if not CONNECTION:
        raise SystemExit("Set DATABASE_URL in your environment or .env file first.")

    with psycopg2.connect(CONNECTION) as conn, conn.cursor() as cursor:
        cursor.execute(CREATE_EXTENSION)
        cursor.execute(CREATE_PODCAST_TABLE)
        cursor.execute(CREATE_SEGMENT_TABLE)

    print("Created podcast and podcast_segment tables.")


if __name__ == "__main__":
    main()


