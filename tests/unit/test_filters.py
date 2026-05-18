from pathlib import Path

from impact_agent.indexer.filters import should_index_file


def test_should_index_frontend_code_file() -> None:
    assert should_index_file(Path("src/App.vue"))


def test_should_not_index_dependency_file() -> None:
    assert not should_index_file(Path("node_modules/pkg/index.ts"))


def test_should_not_index_virtualenv_file() -> None:
    assert not should_index_file(Path(".venv/lib/site-packages/pkg/index.ts"))


def test_should_not_index_env_file() -> None:
    assert not should_index_file(Path(".env"))


def test_should_not_index_test_or_mock_files() -> None:
    assert not should_index_file(Path("tests/fixtures/vue_basic/src/App.vue"))
    assert not should_index_file(Path("src/api/mock.js"))
    assert not should_index_file(Path("src/setupTests.js"))
    assert not should_index_file(Path("src/App.spec.ts"))
    assert not should_index_file(Path("src/App.test.tsx"))
    assert not should_index_file(Path("src/__mocks__/order.ts"))
