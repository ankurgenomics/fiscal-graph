"""Unit tests for api.py's structure and its no-API-key-needed guarantees.

No LLM calls -- /health never touches the supervisor, and importing api.py
must never build the graph or require a key. The /query route itself is not
exercised here since answering it requires a real model call.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

import api


def test_importing_api_does_not_build_the_graph():
    assert api._graph is None


def test_health_endpoint_does_not_require_a_graph():
    client = TestClient(api.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert api._graph is None


def test_query_route_is_registered():
    paths = {route.path for route in api.app.routes}
    assert "/query" in paths
    assert "/health" in paths
