import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from app.config import settings


class SessionStore:
    """
    Persistência de sessões de conversa em SQLite.

    Guarda:
    - estado atual da conversa;
    - assunto jurídico selecionado;
    - dados coletados durante o atendimento;
    - horário da última atualização.

    A implementação mantém compatibilidade com chamadas antigas como:

        await session_store.set(phone, "menu")
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.SESSIONS_DB_PATH

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """
        Cria a tabela e aplica uma migração simples em bancos já existentes.
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    phone TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    topic TEXT,
                    data TEXT NOT NULL DEFAULT '{}',
                    updated_at INTEGER NOT NULL
                )
                """
            )

            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }

            if "topic" not in columns:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN topic TEXT"
                )

            if "data" not in columns:
                conn.execute(
                    """
                    ALTER TABLE sessions
                    ADD COLUMN data TEXT NOT NULL DEFAULT '{}'
                    """
                )

            conn.commit()

    # ------------------------------------------------------------------
    # Operações síncronas
    # ------------------------------------------------------------------

    def _get_sync(self, phone: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT state, topic, data, updated_at
                FROM sessions
                WHERE phone = ?
                """,
                (phone,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        state, topic, raw_data, updated_at = row

        try:
            data = json.loads(raw_data or "{}")
        except (json.JSONDecodeError, TypeError):
            data = {}

        return {
            "state": state,
            "topic": topic,
            "data": data,
            "updated_at": updated_at,
        }

    def _set_sync(
        self,
        phone: str,
        state: str,
        topic: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ):
        """
        Atualiza a sessão.

        Quando topic ou data não são informados, preserva os valores
        existentes no banco.
        """

        current = self._get_sync(phone)

        resolved_topic = (
            topic
            if topic is not None
            else current.get("topic") if current else None
        )

        resolved_data = (
            data
            if data is not None
            else current.get("data", {}) if current else {}
        )

        serialized_data = json.dumps(
            resolved_data,
            ensure_ascii=False,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    phone,
                    state,
                    topic,
                    data,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    state = excluded.state,
                    topic = excluded.topic,
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (
                    phone,
                    state,
                    resolved_topic,
                    serialized_data,
                    int(time.time()),
                ),
            )
            conn.commit()

    def _delete_sync(self, phone: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM sessions WHERE phone = ?",
                (phone,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # API assíncrona
    # ------------------------------------------------------------------

    async def get(self, phone: str) -> Optional[dict]:
        """
        Retorna:

        {
            "state": "...",
            "topic": "...",
            "data": {...},
            "updated_at": 123456789
        }

        Retorna None quando a sessão não existe ou expirou.
        """

        session = await asyncio.to_thread(
            self._get_sync,
            phone,
        )

        if not session:
            return None

        age_seconds = time.time() - session["updated_at"]

        if age_seconds > settings.SESSION_TIMEOUT_SECONDS:
            await asyncio.to_thread(
                self._delete_sync,
                phone,
            )
            return None

        return session

    async def set(
        self,
        phone: str,
        state: str,
        topic: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ):
        await asyncio.to_thread(
            self._set_sync,
            phone,
            state,
            topic,
            data,
        )

    async def update_data(
        self,
        phone: str,
        **fields: Any,
    ) -> Optional[dict]:
        """
        Atualiza somente campos específicos de data.

        Exemplo:

            await store.update_data(
                phone,
                name="Maria",
                cpf="12345678900",
            )
        """

        session = await self.get(phone)

        if not session:
            return None

        data = dict(session.get("data") or {})
        data.update(fields)

        await self.set(
            phone=phone,
            state=session["state"],
            topic=session.get("topic"),
            data=data,
        )

        session["data"] = data
        session["updated_at"] = int(time.time())

        return session

    async def clear(self, phone: str):
        await asyncio.to_thread(
            self._delete_sync,
            phone,
        )