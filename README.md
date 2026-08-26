# Agentic RAG Service

[![CI](https://github.com/kursadbilgin/agentic-rag-service/actions/workflows/ci.yml/badge.svg)](https://github.com/kursadbilgin/agentic-rag-service/actions/workflows/ci.yml)

An async FastAPI service that answers questions over your documents using a self-correcting LangGraph agent: it grades retrieved context, rewrites the query when needed, and returns sourced answers — or honestly says it couldn't find one.

Naive RAG pushes whatever the vector store returns straight into the prompt. This service treats retrieval quality as something to be checked: a grader node decides whether the context can actually answer the question, a rewrite node gets a bounded number of second chances, and when both fail the agent says so instead of inventing an answer.

## How it works

```mermaid
flowchart LR
    A([START]) --> R[retrieve]
    R --> G{grade_documents}
    G -- relevant --> N[generate]
    G -- irrelevant, budget left --> W[rewrite_query]
    G -- budget spent / no documents --> U[give_up]
    W --> R
    N --> Z([END])
    U --> Z
```

| Node | What it does |
|---|---|
| `retrieve` | Similarity search over pgvector, `RETRIEVAL_TOP_K` chunks |
| `grade_documents` | One LLM call: can this context answer the question? `yes`/`no` |
| `rewrite_query` | Reformulates the query for semantic search, increments the counter |
| `generate` | Answers strictly from context, collects `source` metadata |
| `give_up` | Returns a "not found" answer with no sources |

The rewrite budget (`MAX_QUERY_REWRITES`) is copied into the graph state, which keeps routing a pure function — it is unit tested without an LLM, a database or an API key.

## Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Uvicorn (async end to end) | Automatic OpenAPI docs, non-blocking I/O |
| Agent | LangGraph `StateGraph` | Explicit state machine instead of an opaque chain |
| LLM | Anthropic Claude or Google Gemini | Swapped with one env var; code only sees `BaseChatModel` |
| Embeddings | FastEmbed (ONNX, local) | No API key, and retrieval stays identical when the chat provider changes |
| Vector store | PostgreSQL + pgvector | A real database: inspectable with SQL, ready for multiple replicas |
| Config | pydantic-settings | 12-factor: every setting comes from the environment |

## Quickstart

### With Docker

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY (or GOOGLE_API_KEY)
docker compose up -d --build  # postgres + app, app waits until postgres is healthy
curl -s localhost:8000/health
```

### Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d postgres
python -m scripts.ingest                       # loads data/sample_docs/
python -m uvicorn app.main:app --reload
```

Interactive docs: <http://localhost:8000/docs>

## API

```bash
$ curl -s localhost:8000/health
{"status":"ok","llm_provider":"anthropic"}

$ curl -s -X POST localhost:8000/ingest -F "files=@data/sample_docs/faq.md"
{"files":1,"chunks":7}

$ curl -s -X POST localhost:8000/query \
       -H 'content-type: application/json' \
       -d '{"question":"İade ne kadar sürede yapılır?"}'
{"answer":"Onaylanan iadeler, iptal talebinin alınmasından itibaren 7 iş günü içinde ödeme yönteminize yansıtılır. Kredi kartı ödemelerinde bankanın işlem süresiyle birlikte 7-14 takvim gününü bulabilir.",
 "sources":["cancellation_policy.md"]}
```

The `/query` body above is a sample answer over the bundled corpus; wording depends on your documents and model.

- `/ingest` accepts `.md` and `.txt`, validates UTF-8, and rejects anything else with `400` and a reason. Re-ingesting the same file is an upsert, not a duplicate.
- `/query` maps agent failures to `502` so upstream provider trouble stays distinguishable from a bug in this service.
- `/health` deliberately touches neither the LLM nor the database.

The sample corpus is three Turkish documents for a fictional travel company (cancellation policy, supplier integration guide, FAQ). Drop your own files in and the service adapts to any domain.

## Configuration

Every setting lives in `.env` (see `.env.example` for the full contract):

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `google` |
| `ANTHROPIC_MODEL` / `GOOGLE_MODEL` | `claude-opus-4-8` / `gemini-2.5-flash` | |
| `DATABASE_URL` | `postgresql+psycopg://rag:rag@localhost:5432/rag` | compose overrides the host to `postgres` |
| `VECTOR_COLLECTION` | `rag_docs` | Table holding the chunks |
| `RETRIEVAL_TOP_K` | `4` | Chunks per similarity search |
| `MAX_QUERY_REWRITES` | `1` | `0` disables self-correction |
| `EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual, 384-dim; rebuild the image with the same `--build-arg EMBED_MODEL` if you change it |

## Design decisions

- **Bounded self-correction.** Rewrites are capped, so worst-case latency and token cost stay predictable. An unbounded correction loop is not something you can operate.
- **Local embeddings.** Switching Claude ↔ Gemini changes exactly one variable in the system: the LLM. Retrieval results are identical, which makes provider comparisons meaningful — and CI needs no API key.
- **Provider registry, not `if/elif`.** `app/llm.py` dispatches through a `dict[str, Callable[[Settings], BaseChatModel]]` with lazy imports, so adding a provider means adding a builder, not editing the factory.
- **Empty retrieval gives up immediately.** Similarity search always returns the k nearest chunks, so an empty result means an empty collection — a rewrite cannot fix that and would only burn a call.
- **Blocking work off the event loop.** Embedding and database writes run in a threadpool; one large upload cannot freeze the service.
- **Deterministic chunk IDs.** `uuid5(source + content hash)` turns ingestion into an upsert, so re-running it never duplicates the knowledge base.
- **Health that means one thing.** `/health` answers "is my process up", not "is my upstream healthy" — a slow provider must not get the pod killed.

## Tests

```bash
ruff check . && pytest -q     # 14 passed
```

The suite runs with **no API key, no network and no database**: `FakeListChatModel` and a stub retriever replace the outside world while the real LangGraph routing executes. Covered: chunking and metadata, upsert IDs, all four routing decisions, the three agent scenarios (answer / rewrite-then-give-up / empty retrieval), and every endpoint including the `400`, `422` and `502` paths.

## Project layout

```
app/
  agent/graph.py   corrective RAG state machine
  config.py        pydantic-settings contract
  llm.py           provider registry
  retriever.py     pgvector store + FastEmbed embeddings
  ingest.py        load / split / upsert
  main.py          FastAPI endpoints
  schemas.py       request & response models
scripts/ingest.py  bulk-load data/sample_docs/
tests/             unit, agent-routing and API tests
```
