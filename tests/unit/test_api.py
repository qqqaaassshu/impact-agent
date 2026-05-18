from fastapi.testclient import TestClient

from impact_agent.api.app import create_app
from impact_agent.config import get_settings


def test_health_check() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_index_status_is_empty_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/index/status")

    assert response.status_code == 200
    assert response.json()["status"] == "empty"


def test_index_build_and_status(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "App.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")

    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    build_response = client.post("/api/index/build", json={"repo_root": str(repo)})
    status_response = client.get("/api/index/status")

    assert build_response.status_code == 200
    assert build_response.json()["indexed_files"] == 1
    assert status_response.json()["status"] == "ready"
    assert status_response.json()["indexed_files"] == 1


def test_search_text_after_index_build(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "App.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")

    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    client.post("/api/index/build", json={"repo_root": str(repo)})
    response = client.post("/api/search/text", json={"query": "price"})

    assert response.status_code == 200
    assert response.json()[0]["file"] == "src/App.vue"


def test_analyze_after_index_build(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "QuoteCard.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")

    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    client.post("/api/index/build", json={"repo_root": str(repo)})
    response = client.post(
        "/api/analyze",
        json={"repo_root": str(repo), "requirement": "price 字段从分改成元"},
    )

    assert response.status_code == 200
    assert response.json()["uncertain"][0]["file"] == "src/QuoteCard.vue"


def test_stream_analyze_after_index_build(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "QuoteCard.vue").write_text("<template>{{ price }}</template>", encoding="utf-8")

    monkeypatch.setenv("IMPACT_AGENT_DATA_DIR", str(tmp_path / ".impact-agent"))
    get_settings.cache_clear()
    client = TestClient(create_app())

    client.post("/api/index/build", json={"repo_root": str(repo)})
    response = client.post(
        "/api/analyze/stream",
        json={"repo_root": str(repo), "requirement": "price 字段从分改成元"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert '"type": "report"' in response.text
    assert "src/QuoteCard.vue" in response.text
