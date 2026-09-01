import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client():
    return TestClient(app)


# -------------------------------------------------
# main.py
# -------------------------------------------------

class TestMain:
    def test_root(self, client, monkeypatch):
        monkeypatch.setattr(settings, "APP_NAME", "TestApp")
        monkeypatch.setattr(settings, "BUSINESS_NAME", "TestBiz")
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["application"] == "TestApp"
        assert body["business"] == "TestBiz"
        assert body["provider"] == "meta"
        assert body["status"] == "running"

    def test_health(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "provider": "baileys"}

    def test_docs_available(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "openapi" in r.json()


# -------------------------------------------------
# webhook Meta GET verification
# -------------------------------------------------

class TestWebhookVerify:
    def test_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "verify_token", "secret123")
        monkeypatch.setattr(settings, "VERIFY_TOKEN", "secret123")
        r = client.get("/webhook?hub.mode=subscribe&hub.verify_token=secret123&hub.challenge=12345")
        assert r.status_code == 200
        assert r.text == "12345"
        assert r.headers["content-type"].startswith("text/plain")

    def test_wrong_token(self, client, monkeypatch):
        monkeypatch.setattr(settings, "verify_token", "secret123")
        r = client.get("/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=12345")
        assert r.status_code == 403
        assert r.json()["detail"] == "Token inválido"

    def test_missing_mode(self, client, monkeypatch):
        monkeypatch.setattr(settings, "verify_token", "secret123")
        r = client.get("/webhook?hub.verify_token=secret123&hub.challenge=12345")
        assert r.status_code == 403

    def test_missing_challenge(self, client, monkeypatch):
        monkeypatch.setattr(settings, "verify_token", "secret123")
        r = client.get("/webhook?hub.mode=subscribe&hub.verify_token=secret123")
        assert r.status_code == 403


# -------------------------------------------------
# webhook Meta POST
# -------------------------------------------------

class TestWebhookPost:
    def test_received(self, client):
        payload = {"object": "whatsapp_business_account", "entry": []}
        with patch("app.routes.webhook.conversation.process", new=AsyncMock()) as mock_process:
            r = client.post("/webhook", json=payload)
            assert r.status_code == 200
            assert r.json() == {"status": "received"}
            # background task should have been called
            mock_process.assert_awaited_once_with(payload)

    def test_received_with_messages(self, client):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"from": "5511", "type": "text", "text": {"body": "oi"}}]}}]}]
        }
        with patch("app.routes.webhook.conversation.process", new=AsyncMock()) as mock_process:
            r = client.post("/webhook", json=payload)
            assert r.status_code == 200
            mock_process.assert_awaited_once()


# -------------------------------------------------
# connector Baileys
# -------------------------------------------------

class TestConnector:
    def test_success(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        with patch("app.routes.connector.conversation.process_connector", new=AsyncMock()) as mock_proc:
            r = client.post(
                "/webhook/connector",
                json={"from": "5511999999999@lid", "text": "Oi"},
                headers={"Authorization": "Bearer sec123"},
            )
            assert r.status_code == 200
            assert r.json() == {"status": "received"}
            mock_proc.assert_awaited_once_with({"from": "5511999999999@lid", "text": "Oi"})

    def test_trims_sender_and_text(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        with patch("app.routes.connector.conversation.process_connector", new=AsyncMock()) as mock_proc:
            r = client.post(
                "/webhook/connector",
                json={"from": "  5511@lid ", "text": "  Olá "},
                headers={"Authorization": "Bearer sec123"},
            )
            assert r.status_code == 200
            mock_proc.assert_awaited_once_with({"from": "5511@lid", "text": "Olá"})

    def test_unauthorized_missing_header(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        r = client.post("/webhook/connector", json={"from": "5511", "text": "Oi"})
        assert r.status_code == 401

    def test_unauthorized_wrong_token(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        r = client.post(
            "/webhook/connector",
            json={"from": "5511", "text": "Oi"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert r.status_code == 401

    def test_empty_from_422(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        r = client.post(
            "/webhook/connector",
            json={"from": "   ", "text": "Oi"},
            headers={"Authorization": "Bearer sec123"},
        )
        assert r.status_code == 422
        assert "from" in r.json()["detail"].lower()

    def test_empty_text_422(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        r = client.post(
            "/webhook/connector",
            json={"from": "5511", "text": "   "},
            headers={"Authorization": "Bearer sec123"},
        )
        assert r.status_code == 422
        assert "text" in r.json()["detail"].lower()

    def test_pydantic_validation_missing_field(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        r = client.post(
            "/webhook/connector",
            json={"from": "5511"},  # missing text
            headers={"Authorization": "Bearer sec123"},
        )
        assert r.status_code == 422

    def test_process_exception_returns_500(self, client, monkeypatch):
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec123")
        monkeypatch.setattr(settings, "connector_secret", "sec123")
        with patch("app.routes.connector.conversation.process_connector", new=AsyncMock(side_effect=Exception("boom"))):
            r = client.post(
                "/webhook/connector",
                json={"from": "5511", "text": "Oi"},
                headers={"Authorization": "Bearer sec123"},
            )
            assert r.status_code == 500
            assert "Erro interno" in r.json()["detail"]
