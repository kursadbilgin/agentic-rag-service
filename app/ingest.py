import hashlib
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.retriever import get_vectorstore

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Separators ordered for markdown: break at headings first, then paragraphs, lines, words.
_SPLITTER = RecursiveCharacterTextSplitter(
    separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    keep_separator=True,
)


def load_file(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text, metadata={"source": path.name})]


def split_documents(docs: list[Document]) -> list[Document]:
    return _SPLITTER.split_documents(docs)


def _chunk_id(chunk: Document) -> str:
    # Deterministic UUID5 from source + content hash — pgvector's langchain_id column is UUID typed.
    # Upsert semantics preserved: same content always maps to the same UUID.
    digest = hashlib.sha256(chunk.page_content.encode()).hexdigest()[:16]
    key = f"{chunk.metadata['source']}:{digest}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def ingest_files(paths: list[Path]) -> int:
    docs: list[Document] = []
    for p in paths:
        docs.extend(load_file(p))

    chunks = split_documents(docs)
    ids = [_chunk_id(c) for c in chunks]

    vs = get_vectorstore()
    vs.add_documents(chunks, ids=ids)

    return len(chunks)
