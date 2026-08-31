import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_sessions.db")


@pytest.fixture
def mock_whatsapp():
    whatsapp = AsyncMock()
    whatsapp.send_text = AsyncMock()
    whatsapp.send_interactive_list = AsyncMock()
    whatsapp.send_buttons = AsyncMock()
    whatsapp.mark_as_read = AsyncMock()
    # compat with provider check
    whatsapp._is_meta = lambda: False
    return whatsapp


@pytest.fixture
def temp_sessions_db(monkeypatch, tmp_db_path):
    """
    Isola SessionStore para não sujar data/sessions.db
    """
    monkeypatch.setenv("SESSIONS_DB_PATH", tmp_db_path)
    # reload settings to pick env
    import importlib, app.config
    importlib.reload(app.config)
    import app.services.session_store
    importlib.reload(app.services.session_store)
    yield tmp_db_path
    # cleanup reload original
    if "SESSIONS_DB_PATH" in os.environ:
        del os.environ["SESSIONS_DB_PATH"]
    importlib.reload(app.config)
    importlib.reload(app.services.session_store)
