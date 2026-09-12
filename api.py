"""Minimal API surface for Part 3's multi-agent supervisor.

One endpoint, POST /query, wraps part3_supervisor.py's build_supervisor() and
run_query() so the multi-agent system is callable as a service, not only as a
script. The supervisor graph is built lazily, on first request, so importing
this module never requires an API key or makes a network call.

Run: uvicorn api:app --reload
"""
from fastapi import FastAPI
from pydantic import BaseModel

from part3_supervisor import build_supervisor, run_query

app = FastAPI(title="Fiscal Graph API")
_graph = None


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    agents_invoked: list[str]


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_supervisor()
    return _graph


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    graph = _get_graph()
    answer, trace = run_query(graph, request.query)
    agents_invoked = sorted(set(t["actor"] for t in trace) - {"user", "supervisor"})
    return QueryResponse(answer=answer, agents_invoked=agents_invoked)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
