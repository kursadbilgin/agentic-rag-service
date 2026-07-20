import warnings
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_postgres import PGEngine, PGVectorStore
from sqlalchemy.exc import ProgrammingError

from app.config import get_settings


class FastEmbedEmbeddings(Embeddings):
    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding  # noqa: PLC0415

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


@lru_cache(maxsize=1)
def get_vectorstore() -> PGVectorStore:
    settings = get_settings()
    embeddings = FastEmbedEmbeddings(model_name=settings.embed_model)
    engine = PGEngine.from_connection_string(url=settings.database_url)
    try:
        engine.init_vectorstore_table(
            table_name=settings.vector_collection,
            vector_size=len(embeddings.embed_query("dimension probe")),
        )
    except ProgrammingError:
        pass
    return PGVectorStore.create_sync(
        engine=engine,
        table_name=settings.vector_collection,
        embedding_service=embeddings,
    )


def get_retriever() -> VectorStoreRetriever:
    settings = get_settings()
    return get_vectorstore().as_retriever(
        search_kwargs={"k": settings.retrieval_top_k},
    )
