"""Run the six exact-L2 recommendation queries from the assignment."""

import os
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv()
CONNECTION = os.getenv("DATABASE_URL")

SEGMENT_COLUMNS = ("Podcast", "Segment ID", "Segment text", "Start (s)", "End (s)", "L2 distance")
EPISODE_COLUMNS = ("Podcast", "L2 distance")

SIMILAR_SEGMENTS = """
SELECT p.title, s.id, s.content, s.start_time, s.end_time,
       s.embedding <-> target.embedding AS distance
FROM podcast_segment AS target
JOIN podcast_segment AS s ON s.id <> target.id
JOIN podcast AS p ON p.id = s.podcast_id
WHERE target.id = %s
ORDER BY s.embedding <-> target.embedding ASC
LIMIT 5
"""

DISSIMILAR_SEGMENTS = """
SELECT p.title, s.id, s.content, s.start_time, s.end_time,
       s.embedding <-> target.embedding AS distance
FROM podcast_segment AS target
JOIN podcast_segment AS s ON s.id <> target.id
JOIN podcast AS p ON p.id = s.podcast_id
WHERE target.id = %s
ORDER BY s.embedding <-> target.embedding DESC
LIMIT 5
"""

SIMILAR_EPISODES_TO_SEGMENT = """
WITH episode_vectors AS (
    SELECT podcast_id, AVG(embedding) AS embedding
    FROM podcast_segment
    GROUP BY podcast_id
)
SELECT p.title, ev.embedding <-> target.embedding AS distance
FROM podcast_segment AS target
JOIN episode_vectors AS ev ON ev.podcast_id <> target.podcast_id
JOIN podcast AS p ON p.id = ev.podcast_id
WHERE target.id = %s
ORDER BY ev.embedding <-> target.embedding ASC
LIMIT 5
"""

SIMILAR_EPISODES_TO_EPISODE = """
WITH episode_vectors AS (
    SELECT podcast_id, AVG(embedding) AS embedding
    FROM podcast_segment
    GROUP BY podcast_id
), target AS (
    SELECT embedding FROM episode_vectors WHERE podcast_id = %s
)
SELECT p.title, ev.embedding <-> target.embedding AS distance
FROM episode_vectors AS ev
CROSS JOIN target
JOIN podcast AS p ON p.id = ev.podcast_id
WHERE ev.podcast_id <> %s
ORDER BY ev.embedding <-> target.embedding ASC
LIMIT 5
"""

QUESTIONS = (
    ("Q1 · Five most similar segments to 267:476", SIMILAR_SEGMENTS, ("267:476",), SEGMENT_COLUMNS),
    ("Q2 · Five most dissimilar segments to 267:476", DISSIMILAR_SEGMENTS, ("267:476",), SEGMENT_COLUMNS),
    ("Q3 · Five most similar segments to 48:511", SIMILAR_SEGMENTS, ("48:511",), SEGMENT_COLUMNS),
    ("Q4 · Five most similar segments to 51:56", SIMILAR_SEGMENTS, ("51:56",), SEGMENT_COLUMNS),
    ("Q5a · Five closest episodes to segment 267:476", SIMILAR_EPISODES_TO_SEGMENT, ("267:476",), EPISODE_COLUMNS),
    ("Q5b · Five closest episodes to segment 48:511", SIMILAR_EPISODES_TO_SEGMENT, ("48:511",), EPISODE_COLUMNS),
    ("Q5c · Five closest episodes to segment 51:56", SIMILAR_EPISODES_TO_SEGMENT, ("51:56",), EPISODE_COLUMNS),
    (
        "Q6 · Five closest episodes to VeH7qKZr0WI",
        SIMILAR_EPISODES_TO_EPISODE,
        ("VeH7qKZr0WI", "VeH7qKZr0WI"),
        EPISODE_COLUMNS,
    ),
)


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def to_markdown(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(format_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def fetch_results() -> list[tuple[str, tuple[str, ...], list[tuple[Any, ...]]]]:
    if not CONNECTION:
        raise SystemExit("Set DATABASE_URL in your environment or .env file first.")

    results = []
    with psycopg2.connect(CONNECTION) as conn, conn.cursor() as cursor:
        for title, query, params, headers in QUESTIONS:
            cursor.execute(query, params)
            results.append((title, headers, cursor.fetchall()))
    return results


def main() -> None:
    sections: list[str] = [
        "# Podcast recommender query results",
        "\nDistances use pgvector's `<->` L2 operator. Each query excludes its source segment or episode.",
    ]
    for title, headers, rows in fetch_results():
        sections.extend((f"\n## {title}", "\n" + to_markdown(headers, rows)))

    output = "\n".join(sections) + "\n"
    results_path = os.getenv("RESULTS_MARKDOWN", "results.md")
    with open(results_path, "w", encoding="utf-8", newline="\n") as results:
        results.write(output)
    print(output)


if __name__ == "__main__":
    main()
