from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["anthropic", "google"] = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"

    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "rag_docs"

    retrieval_top_k: int = 4
    max_query_rewrites: int = 1

    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
