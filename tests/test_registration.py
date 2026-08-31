import pytest
from datetime import date, timedelta

from app.services.registration import RegistrationFlow


# -------------------------------------------------------------
# Validações puras (sem I/O)
# -------------------------------------------------------------

class TestIsValidName:
    def test_valid_simple(self):
        assert RegistrationFlow._is_valid_name("Maria da Silva") is True

    def test_valid_with_hyphen_and_apostrophe(self):
        assert RegistrationFlow._is_valid_name("Ana Maria D'Ávila") is True
        assert RegistrationFlow._is_valid_name("João Pedro-Silva") is True

    def test_valid_accent(self):
        assert RegistrationFlow._is_valid_name("José da Silva") is True

    def test_invalid_single_part(self):
        assert RegistrationFlow._is_valid_name("Maria") is False

    def test_invalid_too_short(self):
        assert RegistrationFlow._is_valid_name("A B") is False

    def test_invalid_too_long(self):
        assert RegistrationFlow._is_valid_name("A" * 59 + " " + "B" * 61) is False  # 121

    def test_invalid_numbers(self):
        assert RegistrationFlow._is_valid_name("Maria 123") is False

    def test_invalid_special_chars(self):
        assert RegistrationFlow._is_valid_name("Maria @ Silva") is False

    def test_invalid_empty(self):
        assert RegistrationFlow._is_valid_name("") is False


class TestIsValidCpf:
    # CPF válido gerado: 529.982.247-25
    VALID = "52998224725"
    VALID_FORMATTED = "529.982.247-25"

    def test_valid_plain(self):
        assert RegistrationFlow._is_valid_cpf(self.VALID) is True

    def test_valid_with_mask_via_only_digits(self):
        digits = RegistrationFlow._only_digits(self.VALID_FORMATTED)
        assert digits == self.VALID
        assert RegistrationFlow._is_valid_cpf(digits) is True

    def test_invalid_wrong_digit(self):
        assert RegistrationFlow._is_valid_cpf("52998224726") is False

    def test_invalid_repeated(self):
        assert RegistrationFlow._is_valid_cpf("11111111111") is False
        assert RegistrationFlow._is_valid_cpf("00000000000") is False

    def test_invalid_length(self):
        assert RegistrationFlow._is_valid_cpf("1234567890") is False
        assert RegistrationFlow._is_valid_cpf("123456789012") is False

    def test_invalid_non_digit(self):
        assert RegistrationFlow._is_valid_cpf("5299822472a") is False


class TestParseBirthDate:
    def test_valid(self):
        d = RegistrationFlow._parse_birth_date("15/08/1990")
        assert d == date(1990, 8, 15)

    def test_valid_with_spaces(self):
        d = RegistrationFlow._parse_birth_date(" 01/01/2000 ")
        assert d == date(2000, 1, 1)

    def test_invalid_format(self):
        assert RegistrationFlow._parse_birth_date("1990-08-15") is None
        assert RegistrationFlow._parse_birth_date("15-08-1990") is None
        assert RegistrationFlow._parse_birth_date("32/01/2000") is None
        assert RegistrationFlow._parse_birth_date("ab/cd/efgh") is None
        assert RegistrationFlow._parse_birth_date("") is None

    def test_calculate_age(self):
        today = date.today()
        birth = date(today.year - 20, today.month, today.day)
        age = RegistrationFlow._calculate_age(birth)
        assert age == 20

        # aniversário ainda não chegou neste ano
        tomorrow = today + timedelta(days=1)
        # birth = 20 anos atrás, mas com dia/mês de amanhã → 19
        try:
            birth2 = date(today.year - 20, tomorrow.month, tomorrow.day)
        except ValueError:
            # 29/02 edge
            pytest.skip("data inválida para teste de idade")
        assert RegistrationFlow._calculate_age(birth2) == 19


class TestIsValidCity:
    def test_valid(self):
        assert RegistrationFlow._is_valid_city("Manaus/AM") is True
        assert RegistrationFlow._is_valid_city("São Paulo/SP") is True
        assert RegistrationFlow._is_valid_city("Rio de Janeiro/RJ") is True

    def test_valid_lower_uf(self):
        assert RegistrationFlow._is_valid_city("Manaus/am") is True

    def test_valid_with_hyphen(self):
        assert RegistrationFlow._is_valid_city("Mogi das Cruzes/SP") is True

    def test_invalid_missing_slash(self):
        assert RegistrationFlow._is_valid_city("Manaus AM") is False

    def test_invalid_uf_length(self):
        assert RegistrationFlow._is_valid_city("Manaus/A") is False
        assert RegistrationFlow._is_valid_city("Manaus/AMM") is False

    def test_invalid_city_short(self):
        assert RegistrationFlow._is_valid_city("A/AM") is False

    def test_invalid_uf_numeric(self):
        assert RegistrationFlow._is_valid_city("Manaus/1M") is False

    def test_format_city(self):
        assert RegistrationFlow._format_city("manaus/am") == "manaus/AM"
        assert RegistrationFlow._format_city("  são paulo / sp ") == "são paulo/SP"

    def test_only_digits(self):
        assert RegistrationFlow._only_digits("123.456.789-00") == "12345678900"

    def test_normalize_spaces(self):
        assert RegistrationFlow._normalize_spaces("  Maria   da  Silva ") == "Maria da Silva"

    def test_format_cpf(self):
        assert RegistrationFlow._format_cpf("52998224725") == "529.982.247-25"


class TestHandles:
    def test_handles_states(self):
        flow = RegistrationFlow(whatsapp=None, sessions=None)  # type: ignore
        assert flow.handles("collect_name") is True
        assert flow.handles("collect_cpf") is True
        assert flow.handles("collect_birth") is True
        assert flow.handles("collect_city") is True
        assert flow.handles("waiting_human") is False
        assert flow.handles("menu") is False
        assert flow.handles(None) is False

    def test_topic_labels_contains_generic(self):
        for key in ["produtos_servicos", "suporte_tecnico", "financeiro", "informacoes"]:
            assert key in RegistrationFlow.TOPIC_LABELS


# -------------------------------------------------------------
# Fluxo async com mocks (sem SQLite real)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_name_success_transitions(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_NAME_STATE, topic="produtos_servicos", data={})

    session = await store.get(phone)
    await flow._collect_name(phone=phone, text="Maria da Silva", session=session)

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.COLLECT_CPF_STATE
    assert updated["data"]["name"] == "Maria da Silva"
    mock_whatsapp.send_text.assert_called()


@pytest.mark.asyncio
async def test_collect_name_invalid_keeps_state(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_NAME_STATE, topic="produtos_servicos", data={})

    session = await store.get(phone)
    await flow._collect_name(phone=phone, text="Maria", session=session)  # só 1 parte

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.COLLECT_NAME_STATE
    mock_whatsapp.send_text.assert_called()
    assert "não consegui validar" in mock_whatsapp.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_collect_cpf_success(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_CPF_STATE, topic="produtos_servicos", data={"name": "Maria da Silva"})

    session = await store.get(phone)
    await flow._collect_cpf(phone=phone, text="529.982.247-25", session=session)

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.COLLECT_BIRTH_STATE
    assert updated["data"]["cpf"] == "529.982.247-25"


@pytest.mark.asyncio
async def test_collect_cpf_invalid(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_CPF_STATE, topic="produtos_servicos", data={})

    session = await store.get(phone)
    await flow._collect_cpf(phone=phone, text="111.111.111-11", session=session)

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.COLLECT_CPF_STATE


@pytest.mark.asyncio
async def test_collect_birth_future_fails(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_BIRTH_STATE, topic="produtos_servicos", data={})

    session = await store.get(phone)
    future = (date.today() + timedelta(days=10)).strftime("%d/%m/%Y")
    await flow._collect_birth(phone=phone, text=future, session=session)

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.COLLECT_BIRTH_STATE
    assert "futuro" in mock_whatsapp.send_text.call_args[0][1].lower()


@pytest.mark.asyncio
async def test_collect_city_success_finishes(mock_whatsapp, temp_sessions_db):
    from app.services.session_store import SessionStore
    store = SessionStore(db_path=temp_sessions_db)
    flow = RegistrationFlow(whatsapp=mock_whatsapp, sessions=store)
    phone = "5511999999999"
    await store.set(phone=phone, state=RegistrationFlow.COLLECT_CITY_STATE, topic="financeiro", data={"name": "Maria", "cpf": "529.982.247-25", "birth_date": "15/08/1990"})

    session = await store.get(phone)
    await flow._collect_city(phone=phone, text="Manaus/AM", session=session)

    updated = await store.get(phone)
    assert updated["state"] == RegistrationFlow.WAITING_HUMAN_STATE
    assert updated["data"]["city"] == "Manaus/AM"
    # último send_text é o resumo
    assert mock_whatsapp.send_text.call_count >= 1
    last_text = mock_whatsapp.send_text.call_args[0][1]
    assert "Cadastro concluído" in last_text
