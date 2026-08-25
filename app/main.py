import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.agent.graph import answer_question
from app.config import get_settings
from app.ingest import ingest_files
from app.schemas import HealthResponse, IngestResponse, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".md", ".txt"}

app = FastAPI(
    title="Agentic RAG Service",
    description="Question answering over your documents with a self-correcting LangGraph agent.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", llm_provider=get_settings().llm_provider)


@app.post("/ingest", response_model=IngestResponse)
async def ingest(files: list[UploadFile]) -> IngestResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    with tempfile.TemporaryDirectory() as tmpdir:
        paths: list[Path] = []
        for upload in files:
            name = Path(upload.filename or "").name
            if not name:
                raise HTTPException(status_code=400, detail="A file was uploaded without a name.")
            if Path(name).suffix.lower() not in SUPPORTED_SUFFIXES:
                raise HTTPException(
                    status_code=400,
                    detail=f"{name}: unsupported file type. Supported: .md, .txt",
                )

            raw = await upload.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400, detail=f"{name}: file is not valid UTF-8 text."
                ) from exc

            path = Path(tmpdir) / name
            path.write_text(text, encoding="utf-8")
            paths.append(path)

        chunks = await run_in_threadpool(ingest_files, paths)

    return IngestResponse(files=len(paths), chunks=chunks)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    try:
        state = await answer_question(request.question)
    except Exception as exc:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=502, detail=f"Agent run failed: {exc}") from exc

    return QueryResponse(answer=state["answer"], sources=state["sources"])
