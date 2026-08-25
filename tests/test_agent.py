from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

import app.agent.graph as graph_module
from app.agent.graph import NOT_FOUND_MESSAGE, build_graph, route_after_grading

RELEVANT_DOCS = [
    Document(
        page_content="İade işlemleri 7 iş günü içinde tamamlanır.",
        metadata={"source": "cancellation_policy.md"},
    )
]


def _state(documents, **overrides):
    state = {
        "question": "İade ne kadar sürede yapılır?",
        "query": "İade ne kadar sürede yapılır?",
        "documents": documents,
        "rewrites": 0,
        "max_rewrites": 1,
        "relevant": False,
        "answer": "",
        "sources": [],
    }
    state.update(overrides)
    return state


def _patch(monkeypatch, documents, responses):
    model = FakeListChatModel(responses=responses)
    monkeypatch.setattr(graph_module, "get_chat_model", lambda: model)
    monkeypatch.setattr(graph_module, "get_retriever", lambda: RunnableLambda(lambda _: documents))


def test_route_after_grading() -> None:
    assert route_after_grading(_state(RELEVANT_DOCS, relevant=True)) == "generate"
    assert route_after_grading(_state(RELEVANT_DOCS)) == "rewrite_query"
    assert route_after_grading(_state(RELEVANT_DOCS, rewrites=1)) == "give_up"
    assert route_after_grading(_state([])) == "give_up"


async def test_relevant_context_produces_sourced_answer(monkeypatch) -> None:
    _patch(monkeypatch, RELEVANT_DOCS, ["yes", "İade 7 iş günü içinde yapılır."])

    result = await build_graph().ainvoke(_state(RELEVANT_DOCS))

    assert result["answer"] == "İade 7 iş günü içinde yapılır."
    assert result["sources"] == ["cancellation_policy.md"]
    assert result["rewrites"] == 0


async def test_irrelevant_context_rewrites_once_then_gives_up(monkeypatch) -> None:
    _patch(monkeypatch, RELEVANT_DOCS, ["no", "iade süresi kaç iş günü", "no"])

    result = await build_graph().ainvoke(_state(RELEVANT_DOCS))

    assert result["answer"] == NOT_FOUND_MESSAGE
    assert result["sources"] == []
    assert result["rewrites"] == 1
    assert result["query"] == "iade süresi kaç iş günü"


async def test_empty_retrieval_gives_up_without_rewriting(monkeypatch) -> None:
    _patch(monkeypatch, [], [])

    result = await build_graph().ainvoke(_state([]))

    assert result["answer"] == NOT_FOUND_MESSAGE
    assert result["sources"] == []
    assert result["rewrites"] == 0
