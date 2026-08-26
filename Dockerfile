FROM python:3.12-slim

ARG EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

WORKDIR /srv

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBED_MODEL}')"

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
