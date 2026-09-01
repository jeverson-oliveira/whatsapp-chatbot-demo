import pytest
from unittest.mock import AsyncMock, patch

from app.services.menu import MenuService


@pytest.fixture
def mock_whatsapp():
    whatsapp = AsyncMock()
    whatsapp.send_text = AsyncMock()
    whatsapp.send_interactive_list = AsyncMock()
    whatsapp._is_meta = AsyncMock(return_value=False) if False else AsyncMock  # placeholder
    # we will set as MagicMock returning bool for sync check
    from unittest.mock import MagicMock
    whatsapp._is_meta = MagicMock(return_value=False)
    return whatsapp


class TestGetType:
    def test_existing(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        assert svc.get_type("main") == "list"
        assert svc.get_type("produtos_servicos") == "human"

    def test_missing(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        assert svc.get_type("inexistente") is None


class TestShow:
    @pytest.mark.asyncio
    async def test_show_not_found(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        await svc.show("5511999999999", "nao_existe")
        mock_whatsapp.send_text.assert_awaited_once_with(to="5511999999999", text="Opção não encontrada.")

    @pytest.mark.asyncio
    async def test_show_human(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        await svc.show("5511999999999", "produtos_servicos")
        mock_whatsapp.send_text.assert_awaited_once()
        _, kwargs = mock_whatsapp.send_text.call_args
        assert kwargs["to"] == "5511999999999"
        assert "Produtos e Serviços" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_show_human_default_text(self, mock_whatsapp):
        # menu without text key should use default
        fake_menus = {"custom": {"type": "human"}}
        with patch("app.services.menu.MENUS", fake_menus):
            svc = MenuService(mock_whatsapp)
            await svc.show("5511999999999", "custom")
            assert "Encaminhando seu atendimento" in mock_whatsapp.send_text.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_show_list_baileys_calls_text(self, mock_whatsapp):
        mock_whatsapp._is_meta.return_value = False
        svc = MenuService(mock_whatsapp)
        await svc.show("5511999999999", "main")
        # baileys path goes via _send_text_list -> send_text
        mock_whatsapp.send_text.assert_awaited_once()
        text = mock_whatsapp.send_text.call_args[1]["text"]
        assert "1 - Produtos e Serviços" in text
        assert "Digite o número" in text

    @pytest.mark.asyncio
    async def test_show_list_meta_calls_interactive(self, mock_whatsapp):
        mock_whatsapp._is_meta.return_value = True
        svc = MenuService(mock_whatsapp)
        await svc.show("5511999999999", "main")
        mock_whatsapp.send_interactive_list.assert_awaited_once()
        _, kwargs = mock_whatsapp.send_interactive_list.call_args
        assert kwargs["to"] == "5511999999999"
        assert "body" in kwargs
        assert kwargs["button"] == "Ver opções"
        assert len(kwargs["rows"]) == 6

    @pytest.mark.asyncio
    async def test_show_unsupported_type(self, mock_whatsapp):
        fake_menus = {"bad": {"type": "unknown"}}
        with patch("app.services.menu.MENUS", fake_menus):
            svc = MenuService(mock_whatsapp)
            await svc.show("5511999999999", "bad")
            assert "Não foi possível exibir" in mock_whatsapp.send_text.call_args[1]["text"]


class TestSendInteractiveList:
    @pytest.mark.asyncio
    async def test_send_interactive_list_params(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        menu = {
            "body": "Escolha:",
            "button": "Ver",
            "rows": [{"id": "a", "title": "A"}],
            "title": "Header",
            "footer": "Footer",
        }
        await svc._send_interactive_list("5511999999999", menu)
        mock_whatsapp.send_interactive_list.assert_awaited_once_with(
            to="5511999999999",
            body="Escolha:",
            button="Ver",
            rows=[{"id": "a", "title": "A"}],
            header_title="Header",
            footer_text="Footer",
        )

    @pytest.mark.asyncio
    async def test_send_interactive_list_defaults(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        await svc._send_interactive_list("5511999999999", {})
        _, kwargs = mock_whatsapp.send_interactive_list.call_args
        assert kwargs["body"] == "Selecione uma opção:"
        assert kwargs["button"] == "Ver opções"
        assert kwargs["rows"] == []


class TestSendTextList:
    @pytest.mark.asyncio
    async def test_send_text_list_builds_enumerated(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        menu = {
            "body": "Menu:",
            "rows": [{"title": "Opção A"}, {"title": "Opção B"}, {}],
        }
        await svc._send_text_list("5511999999999", menu)
        text = mock_whatsapp.send_text.call_args[1]["text"]
        assert "Menu:" in text
        assert "1 - Opção A" in text
        assert "2 - Opção B" in text
        assert "3 - Opção" in text  # default
        assert "Digite o número" in text

    @pytest.mark.asyncio
    async def test_send_text_list_empty(self, mock_whatsapp):
        svc = MenuService(mock_whatsapp)
        await svc._send_text_list("5511999999999", {})
        text = mock_whatsapp.send_text.call_args[1]["text"]
        assert "Selecione uma opção:" in text


class TestSendHuman:
    @pytest.mark.asyncio
    async def test_send_human_uses_settings(self, mock_whatsapp, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "HUMAN_ATTENDANT_NAME", "Carlos Teste")
        monkeypatch.setattr(settings, "human_attendant", "Carlos Teste")
        svc = MenuService(mock_whatsapp)
        await svc.send_human("5511999999999")
        text = mock_whatsapp.send_text.call_args[1]["text"]
        assert "Carlos Teste" in text
        assert "Obrigado pelo contato" in text

    @pytest.mark.asyncio
    async def test_send_human_default(self, mock_whatsapp, monkeypatch):
        from app.config import settings
        # remove attr to test getattr fallback
        if hasattr(settings, "HUMAN_ATTENDANT_NAME"):
            monkeypatch.delattr(settings, "HUMAN_ATTENDANT_NAME", raising=False)
        svc = MenuService(mock_whatsapp)
        await svc.send_human("5511999999999")
        text = mock_whatsapp.send_text.call_args[1]["text"]
        assert "Equipe de Atendimento" in text or "Obrigado pelo contato" in text
