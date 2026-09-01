import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.conversation import ConversationService
from app.services.session_store import SessionStore
from app.services.registration import RegistrationFlow
from app.services.menu import MenuService
from app.config import settings


@pytest.fixture
def tmp_store(tmp_path):
    return SessionStore(db_path=str(tmp_path / "e2e.db"))


@pytest.fixture
def mock_whatsapp():
    w = AsyncMock()
    w.send_text = AsyncMock()
    w.send_interactive_list = AsyncMock()
    w.send_buttons = AsyncMock()
    w.mark_as_read = AsyncMock()
    w._is_meta = MagicMock(return_value=False)
    return w


@pytest.fixture
def e2e_svc(tmp_store, mock_whatsapp):
    # real registration + menu, mocked whatsapp, tmp store
    svc = ConversationService()
    svc.sessions = tmp_store
    svc.whatsapp = mock_whatsapp
    svc.menu = MenuService(mock_whatsapp)
    # rebind registration to use same store/whatsapp
    svc.registration = RegistrationFlow(whatsapp=mock_whatsapp, sessions=tmp_store)
    return svc


@pytest.mark.asyncio
async def test_e2e_full_happy_path(e2e_svc, mock_whatsapp):
    phone = "5511999999999"
    # 1. oi -> main menu
    await e2e_svc.handle_text(phone, "oi")
    assert mock_whatsapp.send_text.called or mock_whatsapp.send_interactive_list.called
    mock_whatsapp.send_text.reset_mock()
    mock_whatsapp.send_interactive_list.reset_mock()

    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "menu"

    # 2. escolhe 1 -> inicia cadastro nome
    await e2e_svc.handle_text(phone, "1")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_name"
    assert sess["topic"] == "produtos_servicos"
    assert "nome completo" in mock_whatsapp.send_text.call_args[0][1].lower()
    mock_whatsapp.send_text.reset_mock()

    # 3. nome válido
    await e2e_svc.handle_text(phone, "Maria da Silva")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_cpf"
    assert sess["data"]["name"] == "Maria da Silva"
    mock_whatsapp.send_text.reset_mock()

    # 4. cpf válido
    await e2e_svc.handle_text(phone, "529.982.247-25")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_birth"
    assert sess["data"]["cpf"] == "529.982.247-25"
    mock_whatsapp.send_text.reset_mock()

    # 5. nascimento válido
    await e2e_svc.handle_text(phone, "15/08/1990")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_city"
    assert sess["data"]["birth_date"] == "15/08/1990"
    mock_whatsapp.send_text.reset_mock()

    # 6. cidade válida -> waiting_human + resumo
    await e2e_svc.handle_text(phone, "Manaus/AM")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "waiting_human"
    assert sess["data"]["city"] == "Manaus/AM"
    last_text = mock_whatsapp.send_text.call_args[0][1]
    assert "Cadastro concluído" in last_text
    assert "Manaus/AM" in last_text
    assert "Maria da Silva" in last_text

    # 7. mensagem após waiting -> fila
    mock_whatsapp.send_text.reset_mock()
    await e2e_svc.handle_text(phone, "qualquer coisa depois")
    assert "fila de atendimento" in mock_whatsapp.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_e2e_invalid_inputs_keep_state(e2e_svc, mock_whatsapp):
    phone = "5511999999999"
    await e2e_svc.handle_text(phone, "oi")
    await e2e_svc.handle_text(phone, "2")  # suporte_tecnico
    mock_whatsapp.send_text.reset_mock()

    # nome inválido (1 parte) -> permanece collect_name
    await e2e_svc.handle_text(phone, "Maria")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_name"
    assert "não consegui validar" in mock_whatsapp.send_text.call_args[0][1].lower()
    mock_whatsapp.send_text.reset_mock()

    # nome válido para avançar
    await e2e_svc.handle_text(phone, "Maria Silva")
    mock_whatsapp.send_text.reset_mock()

    # cpf inválido
    await e2e_svc.handle_text(phone, "111.111.111-11")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_cpf"
    assert "não parece válido" in mock_whatsapp.send_text.call_args[0][1].lower()
    mock_whatsapp.send_text.reset_mock()

    # cpf válido
    await e2e_svc.handle_text(phone, "52998224725")
    mock_whatsapp.send_text.reset_mock()

    # data inválida
    await e2e_svc.handle_text(phone, "32/13/2000")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_birth"
    mock_whatsapp.send_text.reset_mock()

    # data futura
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=5)).strftime("%d/%m/%Y")
    await e2e_svc.handle_text(phone, future)
    assert "futuro" in mock_whatsapp.send_text.call_args[0][1].lower()
    mock_whatsapp.send_text.reset_mock()

    # cidade inválida
    await e2e_svc.handle_text(phone, "Manaus")
    sess = await e2e_svc.sessions.get(phone)
    # ainda collect_city após falhar? precisamos avançar com data válida antes
    # como ainda estamos em collect_birth, vamos enviar data válida primeiro
    await e2e_svc.handle_text(phone, "01/01/1990")
    mock_whatsapp.send_text.reset_mock()
    await e2e_svc.handle_text(phone, "Manaus")  # sem /UF
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_city"
    assert "não consegui identificar" in mock_whatsapp.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_e2e_interactive_flow(e2e_svc, mock_whatsapp):
    phone = "5511999999999"
    # via interactive (Meta) em vez de texto "1"
    await e2e_svc.handle_text(phone, "oi")
    mock_whatsapp.send_text.reset_mock()
    mock_whatsapp.send_interactive_list.reset_mock()

    # simula seleção via lista
    await e2e_svc.handle_interactive(phone, {"interactive": {"list_reply": {"id": "financeiro"}}})
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_name"
    assert sess["topic"] == "financeiro"


@pytest.mark.asyncio
async def test_e2e_menu_command_resets(e2e_svc, mock_whatsapp):
    phone = "5511999999999"
    await e2e_svc.handle_text(phone, "oi")
    await e2e_svc.handle_text(phone, "1")
    await e2e_svc.handle_text(phone, "Maria da Silva")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "collect_cpf"

    # comando menu no meio do cadastro reseta
    await e2e_svc.handle_text(phone, "menu")
    sess = await e2e_svc.sessions.get(phone)
    assert sess["state"] == "menu"


@pytest.mark.asyncio
async def test_e2e_via_connector_and_process(e2e_svc, mock_whatsapp):
    # testa process_connector -> handle_message -> handle_text
    phone = "5511998887777@lid"
    await e2e_svc.process_connector({"from": phone, "text": "oi"})
    sess = await e2e_svc.sessions.get(phone)
    assert sess is not None
    assert sess["state"] == "menu"

    # testa process Meta com payload real
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [
                        {"from": "5511999999999", "id": "wamid.1", "type": "text", "text": {"body": "oi"}}
                    ]
                }
            }]
        }]
    }
    # usa mock mark_as_read já configurado
    await e2e_svc.process(payload)
    sess2 = await e2e_svc.sessions.get("5511999999999")
    assert sess2["state"] == "menu"


@pytest.mark.asyncio
async def test_registration_start_direct(tmp_store, mock_whatsapp):
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=tmp_store)
    await flow.start("5511999999999", "produtos_servicos")
    sess = await tmp_store.get("5511999999999")
    assert sess["state"] == "collect_name"
    assert sess["topic"] == "produtos_servicos"
    assert "nome completo" in mock_whatsapp.send_text.call_args[0][1].lower()

    # handle desconhecido não quebra
    await flow.handle("5511999999999", "texto", {"state": "unknown"})
    # não deve mudar estado
    sess2 = await tmp_store.get("5511999999999")
    assert sess2["state"] == "collect_name"
