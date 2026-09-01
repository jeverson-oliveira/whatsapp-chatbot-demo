import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.conversation import ConversationService


@pytest.fixture
def svc():
    service = ConversationService()
    # mock all deps
    service.whatsapp = AsyncMock()
    service.whatsapp.send_text = AsyncMock()
    service.whatsapp.mark_as_read = AsyncMock()
    service.menu = AsyncMock()
    service.menu.get_type = MagicMock()
    service.menu.show = AsyncMock()
    service.sessions = AsyncMock()
    service.sessions.get = AsyncMock()
    service.sessions.set = AsyncMock()
    service.sessions.clear = AsyncMock()
    service.registration = AsyncMock()
    service.registration.handles = MagicMock()
    service.registration.handle = AsyncMock()
    service.registration.start = AsyncMock()
    service.registration.WAITING_HUMAN_STATE = "waiting_human"
    return service


# -------------------------------------------------
# process (Meta)
# -------------------------------------------------

@pytest.mark.asyncio
async def test_process_ignores_non_whatsapp(svc):
    await svc.process({"object": "not_whatsapp"})
    svc.handle_message = AsyncMock()
    await svc.process({"object": "other"})
    # handle_message não deve ser chamado
    svc.handle_message.assert_not_called() if hasattr(svc, 'handle_message') else None


@pytest.mark.asyncio
async def test_process_handles_messages_and_statuses(svc):
    svc.handle_message = AsyncMock()
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"id": "1", "status": "delivered"}],
                    "contacts": [{"wa_id": "5511"}],
                    "metadata": {"phone_number_id": "123"},
                    "messages": [
                        {"from": "5511999999999", "id": "wamid.1", "type": "text", "text": {"body": "oi"}},
                        {"from": "5511999999999", "id": "wamid.2", "type": "text", "text": {"body": "2"}},
                    ]
                }
            }]
        }]
    }
    await svc.process(payload)
    assert svc.handle_message.call_count == 2
    assert svc.whatsapp.mark_as_read.call_count == 2


@pytest.mark.asyncio
async def test_process_mark_as_read_exception_swallowed(svc):
    svc.handle_message = AsyncMock()
    svc.whatsapp.mark_as_read.side_effect = Exception("fail")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"from": "5511999999999", "id": "wamid.1", "type": "text", "text": {"body": "oi"}}]}}]}]
    }
    await svc.process(payload)  # não deve levantar
    svc.handle_message.assert_called_once()


@pytest.mark.asyncio
async def test_process_exception_handled(svc):
    # force exception dentro do loop
    svc.handle_message = AsyncMock(side_effect=Exception("boom"))
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"from": "5511999999999", "type": "text", "text": {"body": "oi"}}]}}]}]
    }
    # process tem try/except geral, não deve propagar
    await svc.process(payload)


# -------------------------------------------------
# process_connector (Baileys)
# -------------------------------------------------

@pytest.mark.asyncio
async def test_process_connector_success(svc):
    svc.handle_message = AsyncMock()
    await svc.process_connector({"from": " 5511999999999 ", "text": " Oi "})
    svc.handle_message.assert_called_once()
    msg = svc.handle_message.call_args[0][0]
    assert msg["from"] == "5511999999999"
    assert msg["text"]["body"] == "Oi"

@pytest.mark.asyncio
async def test_process_connector_missing_from(svc):
    with pytest.raises(ValueError):
        await svc.process_connector({"text": "Oi"})

@pytest.mark.asyncio
async def test_process_connector_empty_text(svc):
    svc.handle_message = AsyncMock()
    await svc.process_connector({"from": "5511999999999", "text": "   "})
    svc.handle_message.assert_not_called()

@pytest.mark.asyncio
async def test_process_connector_non_string(svc):
    with pytest.raises(ValueError):
        await svc.process_connector({"from": 123, "text": "Oi"})


# -------------------------------------------------
# handle_message
# -------------------------------------------------

@pytest.mark.asyncio
async def test_handle_message_missing_from(svc):
    await svc.handle_message({"type": "text", "text": {"body": "oi"}})
    svc.whatsapp.send_text.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_interactive_routed(svc):
    svc.handle_interactive = AsyncMock()
    await svc.handle_message({"from": "5511999999999", "type": "interactive", "interactive": {}})
    svc.handle_interactive.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_message_text_routed(svc):
    svc.handle_text = AsyncMock()
    await svc.handle_message({"from": "5511999999999", "type": "text", "text": {"body": "oi"}})
    svc.handle_text.assert_awaited_once_with("5511999999999", "oi")

@pytest.mark.asyncio
async def test_handle_message_exception_calls_safe_notify(svc):
    svc.handle_text = AsyncMock(side_effect=Exception("boom"))
    svc._safe_notify_error = AsyncMock()
    await svc.handle_message({"from": "5511999999999", "type": "text", "text": {"body": "oi"}})
    svc._safe_notify_error.assert_awaited_once_with("5511999999999")

@pytest.mark.asyncio
async def test_extract_text_variants(svc):
    assert svc._extract_text({"text": {"body": " oi "}}) == "oi"
    assert svc._extract_text({"text": " olá "}) == "olá"
    assert svc._extract_text({"text": None}) == ""
    assert svc._extract_text({}) == ""


# -------------------------------------------------
# handle_text
# -------------------------------------------------

@pytest.mark.asyncio
async def test_handle_text_initial_commands_clears_and_shows_menu(svc):
    svc.sessions.get.return_value = {"state": "waiting_human"}
    svc._show_main_menu = AsyncMock()
    for cmd in ["oi", "menu", "olá", "inicio", ""]:
        await svc.handle_text("5511999999999", cmd)
        svc.sessions.clear.assert_called()
        svc._show_main_menu.assert_called()
        svc.sessions.clear.reset_mock()
        svc._show_main_menu.reset_mock()

@pytest.mark.asyncio
async def test_handle_text_no_session_shows_menu(svc):
    svc.sessions.get.return_value = None
    svc._show_main_menu = AsyncMock()
    await svc.handle_text("5511999999999", "qualquer")
    svc._show_main_menu.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_text_delegates_to_registration(svc):
    svc.sessions.get.return_value = {"state": "collect_name", "topic": "financeiro", "data": {}}
    svc.registration.handles.return_value = True
    await svc.handle_text("5511999999999", "Maria da Silva")
    svc.registration.handle.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_text_waiting_human(svc):
    svc.sessions.get.return_value = {"state": "waiting_human"}
    svc.registration.handles.return_value = False
    svc._is_waiting_human = MagicMock(return_value=True)
    svc._notify_waiting_human = AsyncMock()
    await svc.handle_text("5511999999999", "oi extra")
    # initial_commands não, registration não, mas waiting -> notify
    # obs: "oi extra" não é initial, então cai no waiting
    svc._notify_waiting_human.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_text_invalid_option(svc):
    svc.sessions.get.return_value = {"state": "menu"}
    svc.registration.handles.return_value = False
    svc._is_waiting_human = MagicMock(return_value=False)
    svc._notify_invalid_option = AsyncMock()
    await svc.handle_text("5511999999999", "99")
    svc._notify_invalid_option.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_text_valid_option_calls_process_selection(svc):
    svc.sessions.get.return_value = {"state": "menu"}
    svc.registration.handles.return_value = False
    svc._is_waiting_human = MagicMock(return_value=False)
    svc._process_selection = AsyncMock()
    await svc.handle_text("5511999999999", "1")
    svc._process_selection.assert_awaited_once_with(phone="5511999999999", selected="produtos_servicos")

@pytest.mark.asyncio
async def test_handle_text_case_insensitive_trim(svc):
    svc.sessions.get.return_value = {"state": "menu"}
    svc.registration.handles.return_value = False
    svc._is_waiting_human = MagicMock(return_value=False)
    svc._process_selection = AsyncMock()
    await svc.handle_text("5511999999999", "  2  ")
    svc._process_selection.assert_awaited_once_with(phone="5511999999999", selected="suporte_tecnico")


# -------------------------------------------------
# handle_interactive
# -------------------------------------------------

@pytest.mark.asyncio
async def test_handle_interactive_list_reply(svc):
    svc._process_selection = AsyncMock()
    msg = {"interactive": {"list_reply": {"id": "financeiro"}}}
    await svc.handle_interactive("5511999999999", msg)
    svc._process_selection.assert_awaited_once_with(phone="5511999999999", selected="financeiro")

@pytest.mark.asyncio
async def test_handle_interactive_button_reply(svc):
    svc._process_selection = AsyncMock()
    msg = {"interactive": {"button_reply": {"id": "falar_atendente"}}}
    await svc.handle_interactive("5511999999999", msg)
    svc._process_selection.assert_awaited_once_with(phone="5511999999999", selected="falar_atendente")

@pytest.mark.asyncio
async def test_handle_interactive_missing_id(svc):
    svc._process_selection = AsyncMock()
    await svc.handle_interactive("5511999999999", {"interactive": {}})
    svc._process_selection.assert_not_called()

@pytest.mark.asyncio
async def test_handle_interactive_prefers_list_over_button(svc):
    svc._process_selection = AsyncMock()
    msg = {"interactive": {"list_reply": {"id": "a"}, "button_reply": {"id": "b"}}}
    await svc.handle_interactive("5511999999999", msg)
    svc._process_selection.assert_awaited_once_with(phone="5511999999999", selected="a")


# -------------------------------------------------
# _process_selection
# -------------------------------------------------

@pytest.mark.asyncio
async def test_process_selection_not_found(svc):
    svc.menu.get_type.return_value = None
    svc._notify_invalid_option = AsyncMock()
    await svc._process_selection("5511999999999", "invalido")
    svc._notify_invalid_option.assert_awaited_once()

@pytest.mark.asyncio
async def test_process_selection_list_sets_state(svc):
    svc.menu.get_type.return_value = "list"
    await svc._process_selection("5511999999999", "main")
    svc.menu.show.assert_awaited_once_with("5511999999999", "main")
    svc.sessions.set.assert_awaited_once_with(phone="5511999999999", state="menu")
    svc.registration.start.assert_not_called()

@pytest.mark.asyncio
async def test_process_selection_human_starts_registration(svc):
    svc.menu.get_type.return_value = "human"
    await svc._process_selection("5511999999999", "financeiro")
    svc.menu.show.assert_awaited_once()
    svc.registration.start.assert_awaited_once_with(phone="5511999999999", topic="financeiro")


# -------------------------------------------------
# _show_main_menu
# -------------------------------------------------

@pytest.mark.asyncio
async def test_show_main_menu(svc):
    await svc._show_main_menu("5511999999999")
    svc.menu.show.assert_awaited_once_with("5511999999999", "main")
    svc.sessions.set.assert_awaited_once_with(phone="5511999999999", state="menu")


# -------------------------------------------------
# helpers
# -------------------------------------------------

def test_is_waiting_human(svc):
    assert svc._is_waiting_human({"state": "waiting_human"}) is True
    assert svc._is_waiting_human({"state": "menu"}) is False
    assert svc._is_waiting_human(None) is False


@pytest.mark.asyncio
async def test_notify_waiting_human(svc):
    await svc._notify_waiting_human("5511999999999")
    svc.whatsapp.send_text.assert_awaited_once()
    assert "fila de atendimento" in svc.whatsapp.send_text.call_args[0][1]

@pytest.mark.asyncio
async def test_notify_invalid_option(svc):
    await svc._notify_invalid_option("5511999999999")
    assert "Opção inválida" in svc.whatsapp.send_text.call_args[0][1]

@pytest.mark.asyncio
async def test_safe_notify_error_success(svc):
    svc.whatsapp.send_text = AsyncMock()
    await svc._safe_notify_error("5511999999999")
    svc.whatsapp.send_text.assert_awaited_once()

@pytest.mark.asyncio
async def test_safe_notify_error_failure_swallowed(svc):
    svc.whatsapp.send_text = AsyncMock(side_effect=Exception("fail"))
    await svc._safe_notify_error("5511999999999")  # não deve propagar
