from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.llm import get_chat_model
from app.retriever import get_retriever

NOT_FOUND_MESSAGE = (
    "Dokümanlarda bu soruyu yanıtlayacak bilgi bulamadım."
)

_GRADE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You grade whether the retrieved context is sufficient to answer the user's "
            "question. Answer with a single word: 'yes' or 'no'. Answer 'yes' only if the "
            "context contains the facts needed for an answer.",
        ),
        ("human", "Question:\n{question}\n\nContext:\n{context}"),
    ]
)

_ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions strictly from the provided context. Never invent facts "
            "that are not in the context. Reply in the same language as the question and "
            "keep the answer short.",
        ),
        ("human", "Question:\n{question}\n\nContext:\n{context}"),
    ]
)

_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You rewrite a search query for semantic retrieval over a document collection. "
            "Keep the original language, expand implicit terms and return only the rewritten "
            "query without any explanation.",
        ),
        ("human", "{query}"),
    ]
)


class AgentState(TypedDict):
    question: str
    query: str
    documents: list[Document]
    rewrites: int
    max_rewrites: int
    relevant: bool
    answer: str
    sources: list[str]


def _format_documents(documents: list[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}" for doc in documents
    )


async def retrieve(state: AgentState) -> dict:
    documents = await get_retriever().ainvoke(state["query"])
    return {"documents": documents}


async def grade_documents(state: AgentState) -> dict:
    if not state["documents"]:
        return {"relevant": False}

    chain = _GRADE_PROMPT | get_chat_model() | StrOutputParser()
    verdict = await chain.ainvoke(
        {"question": state["question"], "context": _format_documents(state["documents"])}
    )
    return {"relevant": verdict.strip().lower().startswith("yes")}


async def rewrite_query(state: AgentState) -> dict:
    chain = _REWRITE_PROMPT | get_chat_model() | StrOutputParser()
    rewritten = await chain.ainvoke({"query": state["query"]})
    return {"query": rewritten.strip(), "rewrites": state["rewrites"] + 1}


async def generate(state: AgentState) -> dict:
    chain = _ANSWER_PROMPT | get_chat_model() | StrOutputParser()
    answer = await chain.ainvoke(
        {"question": state["question"], "context": _format_documents(state["documents"])}
    )
    sources = sorted({doc.metadata.get("source", "unknown") for doc in state["documents"]})
    return {"answer": answer.strip(), "sources": sources}


async def give_up(state: AgentState) -> dict:
    return {"answer": NOT_FOUND_MESSAGE, "sources": []}


def route_after_grading(state: AgentState) -> Literal["generate", "rewrite_query", "give_up"]:
    if not state["documents"]:
        return "give_up"
    if state["relevant"]:
        return "generate"
    if state["rewrites"] < state["max_rewrites"]:
        return "rewrite_query"
    return "give_up"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("generate", generate)
    graph.add_node("give_up", give_up)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges("grade_documents", route_after_grading)
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", END)
    graph.add_edge("give_up", END)

    return graph.compile()


async def answer_question(question: str) -> AgentState:
    initial: AgentState = {
        "question": question,
        "query": question,
        "documents": [],
        "rewrites": 0,
        "max_rewrites": get_settings().max_query_rewrites,
        "relevant": False,
        "answer": "",
        "sources": [],
    }
    return await build_graph().ainvoke(initial)
