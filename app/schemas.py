from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    llm_provider: str


class IngestResponse(BaseModel):
    files: int
    chunks: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
