import httpx
import pytest

import app.main as main_module
from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def test_health_does_not_touch_llm_or_vector_store(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm_provider": "anthropic"}


async def test_query_returns_answer_and_sources(client, monkeypatch) -> None:
    async def fake_agent(question: str):
        return {"answer": f"cevap: {question}", "sources": ["faq.md"]}

    monkeypatch.setattr(main_module, "answer_question", fake_agent)

    response = await client.post("/query", json={"question": "İade ne kadar sürede yapılır?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "cevap: İade ne kadar sürede yapılır?",
        "sources": ["faq.md"],
    }


async def test_query_maps_agent_failure_to_502(client, monkeypatch) -> None:
    async def failing_agent(question: str):
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(main_module, "answer_question", failing_agent)

    response = await client.post("/query", json={"question": "soru"})

    assert response.status_code == 502
    assert "provider timeout" in response.json()["detail"]


async def test_query_rejects_empty_question(client) -> None:
    assert (await client.post("/query", json={"question": ""})).status_code == 422


async def test_ingest_accepts_supported_files(client, monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ingest_files", lambda paths: 3 * len(paths))

    response = await client.post(
        "/ingest",
        files=[("files", ("faq.md", "## SSS\nİade 7 iş günü.".encode(), "text/markdown"))],
    )

    assert response.status_code == 200
    assert response.json() == {"files": 1, "chunks": 3}


async def test_ingest_rejects_unsupported_extension(client) -> None:
    response = await client.post(
        "/ingest", files=[("files", ("notes.pdf", b"%PDF-1.7", "application/pdf"))]
    )

    assert response.status_code == 400
    assert "notes.pdf" in response.json()["detail"]


async def test_ingest_rejects_non_utf8_file(client) -> None:
    response = await client.post(
        "/ingest", files=[("files", ("notes.txt", b"\xff\xfe\x00bad", "text/plain"))]
    )

    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]
