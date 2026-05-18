from impact_agent.memory.store import MemoryStore


def test_memory_store_initializes_schema(tmp_path) -> None:
    db_path = tmp_path / "memory.sqlite"
    store = MemoryStore(db_path)

    store.initialize()

    assert db_path.exists()
