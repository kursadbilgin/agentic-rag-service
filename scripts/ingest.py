import logging
from pathlib import Path

from app.ingest import ingest_files

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_DOCS_DIR = Path(__file__).parent.parent / "data" / "sample_docs"


def main() -> None:
    paths = [p for p in SAMPLE_DOCS_DIR.iterdir() if p.suffix in {".md", ".txt"}]
    if not paths:
        logger.warning("No .md/.txt files found in %s", SAMPLE_DOCS_DIR)
        return

    chunk_count = ingest_files(paths)
    logger.info("Ingested %d chunks from %d files", chunk_count, len(paths))


if __name__ == "__main__":
    main()
