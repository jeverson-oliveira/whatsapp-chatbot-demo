import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.whatsapp import WhatsAppService
from app.config import settings


def _mock_async_client(mock_response: MagicMock):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    return mock_context, mock_client


def _ok_response():
    m = MagicMock()
    m.is_error = False
    m.status_code = 200
    m.text = '{"success": true}'
    m.raise_for_status = MagicMock()
    return m


def _error_response():
    m = MagicMock()
    m.is_error = True
    m.status_code = 400
    m.text = '{"error": "bad"}'
    m.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("bad", request=MagicMock(), response=m))
    return m


class TestIsMeta:
    def test_is_meta_true(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        svc = WhatsAppService()
        assert svc._is_meta() is True

    def test_is_meta_false_for_baileys(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        svc = WhatsAppService()
        assert svc._is_meta() is False

    def test_meta_url_and_headers(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "META_API_VERSION", "v25.0")
        monkeypatch.setattr(settings, "meta_api_version", "v25.0")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok123")
        monkeypatch.setattr(settings, "whatsapp_token", "tok123")
        svc = WhatsAppService()
        assert svc._meta_url() == "https://graph.facebook.com/v25.0/123/messages"
        assert svc._meta_headers() == {"Authorization": "Bearer tok123", "Content-Type": "application/json"}

    def test_connector_headers(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec")
        monkeypatch.setattr(settings, "connector_secret", "sec")
        svc = WhatsAppService()
        assert svc._connector_headers()["Authorization"] == "Bearer sec"


class TestSendTextMeta:
    @pytest.mark.asyncio
    async def test_send_text_meta_success(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        monkeypatch.setattr(settings, "META_API_VERSION", "v25.0")
        monkeypatch.setattr(settings, "meta_api_version", "v25.0")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_text("5511999999999", "Olá")
        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["type"] == "text"
        assert kwargs["json"]["text"]["body"] == "Olá"
        assert kwargs["headers"]["Authorization"] == "Bearer tok"

    @pytest.mark.asyncio
    async def test_send_text_meta_truncates_4096(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_text("5511999999999", "A" * 5000)
        body = mock_client.post.call_args[1]["json"]["text"]["body"]
        assert len(body) == 4096

    @pytest.mark.asyncio
    async def test_send_text_meta_missing_config_no_request(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "")
        monkeypatch.setattr(settings, "phone_number_id", "")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "")
        monkeypatch.setattr(settings, "whatsapp_token", "")
        svc = WhatsAppService()
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.send_text("5511999999999", "Oi")
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_text_meta_error_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_resp = _error_response()
        mock_ctx, _ = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(httpx.HTTPError):
                await svc.send_text("5511999999999", "Oi")


class TestSendTextBaileys:
    @pytest.mark.asyncio
    async def test_send_text_baileys_success(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        monkeypatch.setattr(settings, "CONNECTOR_URL", "http://localhost:3300")
        monkeypatch.setattr(settings, "connector_url", "http://localhost:3300")
        monkeypatch.setattr(settings, "CONNECTOR_SECRET", "sec")
        monkeypatch.setattr(settings, "connector_secret", "sec")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_text("5511999999999", "Oi Baileys")
        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert args[0] == "http://localhost:3300/send"
        assert kwargs["json"] == {"to": "5511999999999", "text": "Oi Baileys"}

    @pytest.mark.asyncio
    async def test_send_text_baileys_error_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        monkeypatch.setattr(settings, "connector_url", "http://localhost:3300")
        svc = WhatsAppService()
        mock_resp = _error_response()
        mock_ctx, _ = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(httpx.HTTPError):
                await svc.send_text("5511999999999", "Oi")


class TestInteractiveList:
    @pytest.mark.asyncio
    async def test_baileys_fallback_to_text(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        monkeypatch.setattr(settings, "connector_url", "http://c:3300")
        monkeypatch.setattr(settings, "CONNECTOR_URL", "http://c:3300")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_interactive_list("5511999999999", "Escolha:", "Ver opções", [{"id": "a", "title": "Opção A"}, {"id": "b", "title": "Opção B"}])
        # fallback chama send_text -> connector
        mock_client.post.assert_called_once()
        json_body = mock_client.post.call_args[1]["json"]
        assert "1 - Opção A" in json_body["text"]
        assert "2 - Opção B" in json_body["text"]

    @pytest.mark.asyncio
    async def test_meta_success_truncates_and_limits(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        long_body = "B" * 2000
        long_button = "C" * 50
        rows = [{"id": f"id{i}", "title": "T" * 40, "description": "D" * 100} for i in range(12)]  # 12 > 10
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_interactive_list("5511999999999", long_body, long_button, rows, header_title="H" * 100, footer_text="F" * 100)
        payload = mock_client.post.call_args[1]["json"]
        assert len(payload["interactive"]["body"]["text"]) == 1024
        assert len(payload["interactive"]["action"]["button"]) == 20
        assert len(payload["interactive"]["action"]["sections"][0]["rows"]) == 10
        assert len(payload["interactive"]["action"]["sections"][0]["rows"][0]["title"]) == 24
        assert len(payload["interactive"]["action"]["sections"][0]["rows"][0]["description"]) == 72
        assert len(payload["interactive"]["header"]["text"]) == 60

    @pytest.mark.asyncio
    async def test_meta_missing_config_fallback_to_text(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "")
        monkeypatch.setattr(settings, "phone_number_id", "")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "")
        monkeypatch.setattr(settings, "whatsapp_token", "")
        svc = WhatsAppService()
        # deve chamar _send_meta_text que também vai early-return sem request, então nenhum post
        # mas cobre o branch
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.send_interactive_list("5511999999999", "body", "btn", [{"id": "a", "title": "A"}])
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_meta_error_fallback_and_raise(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_err = _error_response()
        # segunda chamada é o fallback _send_meta_text com ok
        mock_ok = _ok_response()
        # precisamos sequenciar: primeira lista falha, segunda fallback ok, mas raise ainda acontece
        # nosso código faz fallback antes de raise, então teremos 2 posts
        # vamos mockar para que o primeiro retorne erro e o segundo ok, mas raise ainda levanta
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[mock_err, mock_ok])
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(httpx.HTTPError):
                await svc.send_interactive_list("5511999999999", "body", "btn", [{"id": "a", "title": "A"}])
        assert mock_client.post.call_count == 2


class TestButtons:
    @pytest.mark.asyncio
    async def test_baileys_fallback(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        monkeypatch.setattr(settings, "connector_url", "http://c:3300")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_buttons("5511999999999", "Escolha", [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}])
        assert mock_client.post.called
        assert mock_client.post.call_args[1]["json"]["text"] == "Escolha"

    @pytest.mark.asyncio
    async def test_meta_success_limits_to_3(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.send_buttons("5511999999999", "B" * 2000, [{"id": f"id{i}", "title": "T" * 30} for i in range(5)])
        payload = mock_client.post.call_args[1]["json"]
        assert len(payload["interactive"]["action"]["buttons"]) == 3
        assert len(payload["interactive"]["action"]["buttons"][0]["reply"]["title"]) == 20
        assert len(payload["interactive"]["body"]["text"]) == 1024

    @pytest.mark.asyncio
    async def test_meta_error_fallback(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_err = _error_response()
        mock_ok = _ok_response()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[mock_err, mock_ok])
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(httpx.HTTPError):
                await svc.send_buttons("5511999999999", "body", [{"id": "a", "title": "A"}])

    @pytest.mark.asyncio
    async def test_meta_missing_config_buttons_fallback(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "")
        monkeypatch.setattr(settings, "phone_number_id", "")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "")
        monkeypatch.setattr(settings, "whatsapp_token", "")
        svc = WhatsAppService()
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.send_buttons("5511999999999", "body", [{"id": "a", "title": "A"}])
            mock_cls.assert_not_called()


class TestMarkAsRead:
    @pytest.mark.asyncio
    async def test_baileys_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "baileys")
        svc = WhatsAppService()
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.mark_as_read("wamid.123")
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_meta_empty_id_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        svc = WhatsAppService()
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.mark_as_read("")
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_meta_missing_config_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "phone_number_id", "")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "")
        svc = WhatsAppService()
        with patch("app.services.whatsapp.httpx.AsyncClient") as mock_cls:
            await svc.mark_as_read("wamid.123")
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_meta_success(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "PHONE_NUMBER_ID", "123")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        monkeypatch.setattr(settings, "WHATSAPP_TOKEN", "tok")
        svc = WhatsAppService()
        mock_resp = _ok_response()
        mock_ctx, mock_client = _mock_async_client(mock_resp)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.mark_as_read("wamid.123")
        mock_client.post.assert_called_once()
        assert mock_client.post.call_args[1]["json"]["message_id"] == "wamid.123"

    @pytest.mark.asyncio
    async def test_meta_exception_swallowed(self, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
        monkeypatch.setattr(settings, "phone_number_id", "123")
        monkeypatch.setattr(settings, "whatsapp_token", "tok")
        svc = WhatsAppService()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("net"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.whatsapp.httpx.AsyncClient", return_value=mock_ctx):
            await svc.mark_as_read("wamid.123")  # não deve levantar
