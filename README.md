# Podcast Vector Recommender

This project loads Lex Fridman podcast segments and their 128-dimensional OpenAI embeddings into PostgreSQL with pgvector, then runs the six L2-nearest-neighbor questions from the CS452 assignment.

## Requirements

- Python 3.10 or newer
- Docker Desktop with Compose, or another PostgreSQL 17 server with pgvector installed
- The course `embedding.zip` and `batch_request*.jsonl` files

## Setup

1. Start PostgreSQL with pgvector:

   ```sh
   docker compose up -d
   ```

2. Copy `.env.example` to `.env`. Change the local password if needed. `.env` is ignored by Git.

3. Install Python dependencies:

   ```sh
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   pip install -r recommender/requirements.txt
   ```

4. Put the supplied `embedding.zip` and `documents.zip` files in `data/` (or unzip them there). The loader reads the archives directly and joins `embedding/*.jsonl` with `documents/batch_request_*.jsonl`. The Hugging Face dataset supplies episode titles and timestamps.

5. Build and load the database, run the questions, and create both `results.md` and `results.pdf`:

   ```sh
   python run_local.py
   ```

On Windows without Docker, `run_local.py` starts the assignment-supported embedded pgserver automatically (included in the requirements). On other platforms, configure Docker Compose or set `DATABASE_URL` for an existing pgvector PostgreSQL server.

`DATA_DIR` and `RESULTS_MARKDOWN` can override the default paths. The segment loader joins request text to embeddings by `custom_id`, accepts either `episode;segment` or `episode:segment`, checks vector dimensions, and uses PostgreSQL `COPY` in bounded batches.

## Query behavior

- Q1 and Q3–Q4 return five nearest segments by Euclidean distance.
- Q2 returns the five farthest segments by Euclidean distance.
- Q5 averages segment vectors by episode, then finds five closest episodes for each input segment. The source episode is omitted.
- Q6 averages segment vectors for each episode and finds the five closest episodes to `VeH7qKZr0WI`. The source episode is omitted.

The report includes the SQL result rows. It is only considered complete after the loader has run against the supplied data and the database returned rows for all questions; no query results are fabricated in the source files.
