# Agentic RAG Service

An async FastAPI service that answers questions over your documents using a self-correcting LangGraph agent: it grades retrieved context, rewrites the query when needed, and returns sourced answers — or honestly says it couldn't find one.
