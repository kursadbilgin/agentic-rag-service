from pathlib import Path

import app.ingest as ingest_module
from app.ingest import load_file, split_documents

MARKDOWN = """# Bilgin Travel

## İade Süresi

İade işlemleri 7 iş günü içinde tamamlanır.

## İptal Koşulları

Otel rezervasyonları 24 saat öncesine kadar ücretsiz iptal edilebilir.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_file_sets_source_metadata(tmp_path: Path) -> None:
    docs = load_file(_write(tmp_path, "policy.md", MARKDOWN))

    assert len(docs) == 1
    assert docs[0].metadata["source"] == "policy.md"
    assert "7 iş günü" in docs[0].page_content


def test_split_documents_preserves_metadata(tmp_path: Path) -> None:
    docs = load_file(_write(tmp_path, "policy.md", MARKDOWN * 20))

    chunks = split_documents(docs)

    assert len(chunks) > 1
    assert all(chunk.metadata["source"] == "policy.md" for chunk in chunks)
    assert all(len(chunk.page_content) <= ingest_module.CHUNK_SIZE for chunk in chunks)


def test_ingest_files_upserts_with_deterministic_ids(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list] = {}

    class FakeVectorStore:
        def add_documents(self, documents, ids):
            captured["documents"] = documents
            captured["ids"] = ids

    monkeypatch.setattr(ingest_module, "get_vectorstore", lambda: FakeVectorStore())

    path = _write(tmp_path, "policy.md", MARKDOWN)
    first = ingest_module.ingest_files([path])
    first_ids = captured["ids"]
    second = ingest_module.ingest_files([path])

    assert first == second == len(first_ids)
    assert first_ids == captured["ids"]
    assert len(set(first_ids)) == len(first_ids)
