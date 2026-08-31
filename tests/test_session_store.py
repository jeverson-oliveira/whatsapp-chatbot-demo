import json
import sqlite3
import time
import asyncio
from pathlib import Path

import pytest

from app.services.session_store import SessionStore


# Helpers

def raw_insert(db_path: str, phone: str, state: str, topic=None, data="{}", updated_at=None):
    if updated_at is None:
        updated_at = int(time.time())
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (phone, state, topic, data, updated_at) VALUES (?,?,?,?,?)",
            (phone, state, topic, data, updated_at),
        )
        conn.commit()


# -------------------------------------------------------------
# Sync API
# -------------------------------------------------------------

class TestInitDb:
    def test_creates_table_and_parent(self, tmp_path: Path):
        db = str(tmp_path / "a" / "b" / "test.db")
        store = SessionStore(db_path=db)
        assert Path(db).exists()
        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            assert {"phone", "state", "topic", "data", "updated_at"} <= cols

    def test_migration_adds_missing_columns(self, tmp_path: Path):
        # cria tabela legada sem topic/data e verifica migração
        db = str(tmp_path / "legacy.db")
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE sessions (phone TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at INTEGER NOT NULL)")
            conn.execute("INSERT INTO sessions (phone, state, updated_at) VALUES ('5511','menu',?)", (int(time.time()),))
            conn.commit()
        # init deve adicionar topic/data
        SessionStore(db_path=db)
        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            assert "topic" in cols
            assert "data" in cols


class TestSyncCrud:
    def test_get_missing_returns_none(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        assert store._get_sync("5511999999999") is None

    def test_set_and_get(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        store._set_sync("5511999999999", "menu", topic="financeiro", data={"name": "Maria"})
        got = store._get_sync("5511999999999")
        assert got["state"] == "menu"
        assert got["topic"] == "financeiro"
        assert got["data"] == {"name": "Maria"}
        assert "updated_at" in got

    def test_set_preserves_topic_and_data_when_none(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        store._set_sync("5511999999999", "menu", topic="financeiro", data={"name": "Maria"})
        # atualiza só state
        store._set_sync("5511999999999", "collect_name")
        got = store._get_sync("5511999999999")
        assert got["state"] == "collect_name"
        assert got["topic"] == "financeiro"
        assert got["data"] == {"name": "Maria"}

    def test_set_overwrites_topic_and_data(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        store._set_sync("5511999999999", "menu", topic="a", data={"x": 1})
        store._set_sync("5511999999999", "menu2", topic="b", data={"y": 2})
        got = store._get_sync("5511999999999")
        assert got["topic"] == "b"
        assert got["data"] == {"y": 2}

    def test_delete(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        store._set_sync("5511999999999", "menu")
        store._delete_sync("5511999999999")
        assert store._get_sync("5511999999999") is None

    def test_get_handles_invalid_json(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        raw_insert(str(tmp_path / "t.db"), "5511999999999", "menu", data="not-json{{{")
        got = store._get_sync("5511999999999")
        assert got["data"] == {}

    def test_data_unicode_preserved(self, tmp_path: Path):
        store = SessionStore(db_path=str(tmp_path / "t.db"))
        store._set_sync("5511999999999", "menu", data={"city": "São Paulo/SP"})
        got = store._get_sync("5511999999999")
        assert got["data"]["city"] == "São Paulo/SP"


# -------------------------------------------------------------
# Async API
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_set_get(tmp_path: Path):
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    await store.set("5511999999999", "menu", topic="suporte_tecnico", data={"a": 1})
    got = await store.get("5511999999999")
    assert got["state"] == "menu"
    assert got["topic"] == "suporte_tecnico"


@pytest.mark.asyncio
async def test_async_get_expired_returns_none_and_deletes(tmp_path: Path, monkeypatch):
    from app.config import settings
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "SESSION_TIMEOUT_SECONDS", 1)
    await store.set("5511999999999", "menu")
    # envelhece manualmente
    with sqlite3.connect(str(tmp_path / "t.db")) as conn:
        conn.execute("UPDATE sessions SET updated_at = ?", (int(time.time()) - 10,))
        conn.commit()
    got = await store.get("5511999999999")
    assert got is None
    # verifica que foi deletado
    assert store._get_sync("5511999999999") is None


@pytest.mark.asyncio
async def test_async_get_not_expired(tmp_path: Path, monkeypatch):
    from app.config import settings
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "SESSION_TIMEOUT_SECONDS", 100)
    await store.set("5511999999999", "menu")
    got = await store.get("5511999999999")
    assert got is not None
    assert got["state"] == "menu"


@pytest.mark.asyncio
async def test_update_data_merges(tmp_path: Path):
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    await store.set("5511999999999", "collect_cpf", data={"name": "Maria"})
    updated = await store.update_data("5511999999999", cpf="529.982.247-25", birth_date="15/08/1990")
    assert updated["data"]["name"] == "Maria"
    assert updated["data"]["cpf"] == "529.982.247-25"
    got = await store.get("5511999999999")
    assert got["data"]["cpf"] == "529.982.247-25"


@pytest.mark.asyncio
async def test_update_data_missing_returns_none(tmp_path: Path):
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    result = await store.update_data("5511999999999", cpf="123")
    assert result is None


@pytest.mark.asyncio
async def test_clear(tmp_path: Path):
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    await store.set("5511999999999", "menu")
    await store.clear("5511999999999")
    assert await store.get("5511999999999") is None
    assert store._get_sync("5511999999999") is None


@pytest.mark.asyncio
async def test_concurrent_sets(tmp_path: Path):
    # garante que to_thread não corrompe
    store = SessionStore(db_path=str(tmp_path / "t.db"))
    await asyncio.gather(
        store.set("5511999999991", "menu"),
        store.set("5511999999992", "menu"),
        store.set("5511999999993", "menu"),
    )
    assert await store.get("5511999999991") is not None
    assert await store.get("5511999999992") is not None
    assert await store.get("5511999999993") is not None
