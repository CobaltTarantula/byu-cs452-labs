"""Load the supplied OpenAI batch files and Hugging Face episode metadata."""

from __future__ import annotations

import csv
import glob
import io
import json
import os
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice, zip_longest
from pathlib import Path
from typing import Any, Iterable, Iterator
from zipfile import ZipFile

import psycopg2
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()
CONNECTION = os.getenv("DATABASE_URL")
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DIMENSIONS = 128
BATCH_SIZE = 5_000
CUSTOM_ID = re.compile(r"^(\d+)[;:](\d+)$")


@dataclass(frozen=True)
class JsonlRef:
    path: Path | None = None
    archive_path: Path | None = None
    member: str | None = None

    @property
    def name(self) -> str:
        return self.path.name if self.path else str(self.member)


@contextmanager
def open_jsonl(source: JsonlRef):
    if source.path is not None:
        with source.path.open(encoding="utf-8") as stream:
            yield stream
        return
    assert source.archive_path is not None and source.member is not None
    with ZipFile(source.archive_path) as archive, archive.open(source.member) as binary:
        with io.TextIOWrapper(binary, encoding="utf-8") as stream:
            yield stream


def find_jsonl(
    file_patterns: tuple[str, ...],
    archive_patterns: tuple[str, ...],
    member_prefixes: tuple[str, ...],
) -> list[JsonlRef]:
    found = [
        JsonlRef(path=Path(path_string))
        for pattern in file_patterns
        for path_string in glob.glob(str(DATA_DIR / pattern))
    ]
    for pattern in archive_patterns:
        for archive_string in glob.glob(str(DATA_DIR / pattern)):
            archive_path = Path(archive_string)
            with ZipFile(archive_path) as archive:
                found.extend(
                    JsonlRef(archive_path=archive_path, member=info.filename)
                    for info in archive.infolist()
                    if info.filename.lower().endswith(".jsonl")
                    and any(info.filename.startswith(prefix) for prefix in member_prefixes)
                )
    return found


def batch_key(source: JsonlRef, request: bool) -> str:
    name = source.member if source.member else source.path.name
    stem = Path(name).stem
    for prefix in ("batch_requests_", "batch_request_", "batch_requests", "batch_request"):
        if request and stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def paired_batches() -> list[tuple[JsonlRef, JsonlRef]]:
    embeddings = find_jsonl(
        ("embedding*.jsonl", "embeddings*.jsonl"),
        ("embedding*.zip", "embeddings*.zip"),
        ("embedding/", "embeddings/"),
    )
    requests = find_jsonl(
        ("batch_request*.jsonl", "batch_requests*.jsonl"),
        ("raw*.zip", "documents*.zip"),
        ("documents/batch_request", "batch_request"),
    )
    embedding_by_key = {batch_key(source, False): source for source in embeddings}
    request_by_key = {batch_key(source, True): source for source in requests}
    if not embedding_by_key or not request_by_key:
        raise FileNotFoundError(f"Need embedding and batch request JSONL files or course ZIP archives in {DATA_DIR}")
    if embedding_by_key.keys() != request_by_key.keys():
        missing_requests = sorted(embedding_by_key.keys() - request_by_key.keys())
        missing_embeddings = sorted(request_by_key.keys() - embedding_by_key.keys())
        raise ValueError(f"JSONL batch files do not match; no requests for {missing_requests[:2]}, no embeddings for {missing_embeddings[:2]}")
    return [(embedding_by_key[key], request_by_key[key]) for key in sorted(embedding_by_key)]


def normalize_id(value: str) -> str:
    """Store the course's documented `episode:segment` IDs consistently."""
    match = CUSTOM_ID.fullmatch(value)
    if not match:
        raise ValueError(f"Unexpected custom_id {value!r}; expected episode:segment")
    return f"{int(match.group(1))}:{int(match.group(2))}"


def load_episode_metadata() -> list[tuple[str, str, list[dict[str, Any]]]]:
    dataset = load_dataset("Whispering-GPT/lex-fridman-podcast", split="train")
    return [
        (str(row["id"]), str(row["title"]), list(row.get("segments", [])))
        for row in dataset
    ]


def iter_segments(
    episodes: list[tuple[str, str, list[dict[str, Any]]]],
) -> Iterator[tuple[Any, ...]]:
    for embedding_ref, request_ref in paired_batches():
        with open_jsonl(embedding_ref) as embedding_stream, open_jsonl(request_ref) as request_stream:
            for line_number, (embedding_line, request_line) in enumerate(
                zip_longest(embedding_stream, request_stream), 1
            ):
                if embedding_line is None or request_line is None:
                    raise ValueError(f"Batch line counts differ in {embedding_ref.name} and {request_ref.name}")
                if not embedding_line.strip() and not request_line.strip():
                    continue
                if not embedding_line.strip() or not request_line.strip():
                    raise ValueError(f"Batch line counts differ in {embedding_ref.name} and {request_ref.name}")
                try:
                    embedding_row = json.loads(embedding_line)
                    request_row = json.loads(request_line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at line {line_number} in {embedding_ref.name}") from exc
                custom_id = normalize_id(str(embedding_row["custom_id"]))
                request_id = normalize_id(str(request_row["custom_id"]))
                if request_id != custom_id:
                    raise ValueError(f"Batch IDs differ at {custom_id} and {request_id}")
                match = CUSTOM_ID.fullmatch(custom_id)
                assert match is not None
                episode_index, segment_index = map(int, match.groups())
                if episode_index >= len(episodes):
                    raise ValueError(f"Episode index {episode_index} in {custom_id} is outside the dataset")
                episode_id, _, episode_segments = episodes[episode_index]
                if segment_index >= len(episode_segments):
                    raise ValueError(f"Segment index {segment_index} in {custom_id} is outside the episode")
                metadata = episode_segments[segment_index]
                response = embedding_row.get("response") or {}
                body = response.get("body") or embedding_row.get("body") or {}
                data = body.get("data") or []
                vector = data[0].get("embedding") if data else body.get("embedding")
                if vector is None or len(vector) != DIMENSIONS:
                    raise ValueError(f"Missing or invalid {DIMENSIONS}-dimensional vector for {custom_id}")
                request_body = request_row.get("body") or {}
                content = request_body.get("input", request_row.get("input"))
                if isinstance(content, list):
                    content = content[0] if content else ""
                yield (
                    custom_id,
                    float(metadata["start"]),
                    float(metadata["end"]),
                    str(content or ""),
                    "[" + ",".join(format(float(value), ".8g") for value in vector) + "]",
                    episode_id,
                )


def chunks(items: Iterable[tuple[Any, ...]], size: int) -> Iterator[list[tuple[Any, ...]]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def main() -> None:
    if not CONNECTION:
        raise SystemExit("Set DATABASE_URL in your environment or .env file first.")
    if not DATA_DIR.is_dir():
        raise SystemExit(f"Create {DATA_DIR} and put the supplied JSONL files or ZIP archives there.")

    episodes = load_episode_metadata()
    batches = paired_batches()
    print(f"Loading {len(episodes)} podcasts from {len(batches)} matched data batches...")
    with psycopg2.connect(CONNECTION) as conn, conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO podcast (id, title) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title",
            [(episode_id, title) for episode_id, title, _ in episodes],
        )
        cursor.execute("CREATE TEMP TABLE podcast_segment_stage (LIKE podcast_segment) ON COMMIT DROP")
        copy_sql = (
            "COPY podcast_segment_stage (id, start_time, end_time, content, embedding, podcast_id) "
            "FROM STDIN WITH (FORMAT CSV)"
        )
        # COPY handles the full dataset efficiently while each batch stays bounded in memory.
        for batch in chunks(iter_segments(episodes), BATCH_SIZE):
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerows(batch)
            buffer.seek(0)
            cursor.copy_expert(copy_sql, buffer)
        cursor.execute(
            """INSERT INTO podcast_segment (id, start_time, end_time, content, embedding, podcast_id)
               SELECT id, start_time, end_time, content, embedding, podcast_id FROM podcast_segment_stage
               ON CONFLICT (id) DO UPDATE SET
                 start_time = EXCLUDED.start_time,
                 end_time = EXCLUDED.end_time,
                 content = EXCLUDED.content,
                 embedding = EXCLUDED.embedding,
                 podcast_id = EXCLUDED.podcast_id"""
        )
        cursor.execute("SELECT COUNT(*) FROM podcast_segment")
        count = cursor.fetchone()[0]
    print(f"Loaded {len(episodes)} podcasts and {count:,} segments.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"Data load failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
