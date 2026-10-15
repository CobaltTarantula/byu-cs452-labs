"""Package source code and the generated report without including local data or credentials."""

from pathlib import Path
from shutil import copy2
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent
SOURCE_FILES = (
    "README.md",
    ".env.example",
    "compose.yaml",
    "create_report.py",
    "run_local.py",
    "recommender/db_build.py",
    "recommender/db_drop.py",
    "recommender/db_insert.py",
    "recommender/db_query.py",
    "recommender/requirements.txt",
    "recommender/utils.py",
)


def main() -> None:
    report = ROOT / "results.pdf"
    if not report.is_file():
        raise SystemExit("Run the project first; results.pdf is missing.")

    pdf_copy = OUTPUT / "podcast_recommender_results.pdf"
    archive_path = OUTPUT / "podcast_recommender_project.zip"
    copy2(report, pdf_copy)
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for relative in SOURCE_FILES:
            source = ROOT / relative
            if not source.is_file():
                raise SystemExit(f"Required source file is missing: {relative}")
            archive.write(source, f"podcast_recommender/{relative}")
        archive.write(report, "podcast_recommender/results.pdf")
    print(f"Wrote {archive_path}")
    print(f"Wrote {pdf_copy}")


if __name__ == "__main__":
    main()
