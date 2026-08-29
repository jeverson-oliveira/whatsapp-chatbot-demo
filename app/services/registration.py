import logging
import re
from datetime import date, datetime
from typing import Any

from app.services.session_store import SessionStore
from app.services.whatsapp import WhatsAppService


logger = logging.getLogger(__name__)


class RegistrationFlow:
    """
    Controla o cadastro inicial do cliente.

    Fluxo:

        nome completo
        ↓
        CPF
        ↓
        data de nascimento
        ↓
        cidade/UF
        ↓
        atendimento humano
    """

    COLLECT_NAME_STATE = "collect_name"
    COLLECT_CPF_STATE = "collect_cpf"
    COLLECT_BIRTH_STATE = "collect_birth"
    COLLECT_CITY_STATE = "collect_city"
    WAITING_HUMAN_STATE = "waiting_human"

    STATES = {
        COLLECT_NAME_STATE,
        COLLECT_CPF_STATE,
        COLLECT_BIRTH_STATE,
        COLLECT_CITY_STATE,
    }

    TOPIC_LABELS = {
        "produtos_servicos": "Produtos e Serviços",
        "suporte_tecnico": "Suporte Técnico",
        "financeiro": "Financeiro",
        "informacoes": "Informações Gerais",
        "falar_atendente": "Falar com atendente",
        "outro_assunto": "Outro Assunto",
        # retrocompatibilidade
        "aposentadorias": "Produtos e Serviços",
        "incapacidade": "Suporte Técnico",
        "assistenciais": "Informações Gerais",
        "pensoes": "Financeiro",
        "revisoes": "Outro Assunto",
        "outros": "Outro Assunto",
    }

    def __init__(
        self,
        whatsapp: WhatsAppService,
        sessions: SessionStore,
    ) -> None:
        self.whatsapp = whatsapp
        self.sessions = sessions

    def handles(
        self,
        state: str | None,
    ) -> bool:
        """
        Informa se o estado pertence ao fluxo de cadastro.
        """

        return state in self.STATES

    async def start(
        self,
        phone: str,
        topic: str,
    ) -> None:
        """
        Inicia um novo cadastro.
        """

        await self.sessions.set(
            phone=phone,
            state=self.COLLECT_NAME_STATE,
            topic=topic,
            data={},
        )

        await self.whatsapp.send_text(
            phone,
            "Antes de prosseguirmos, precisamos realizar "
            "um breve cadastro.\n\n"
            "Qual é o seu nome completo?",
        )

        logger.info(
            "Cadastro iniciado: phone=%s topic=%s",
            phone,
            topic,
        )

    async def handle(
        self,
        phone: str,
        text: str,
        session: dict[str, Any],
    ) -> None:
        """
        Encaminha a resposta para a etapa atual do cadastro.
        """

        state = session.get("state")

        handlers = {
            self.COLLECT_NAME_STATE: self._collect_name,
            self.COLLECT_CPF_STATE: self._collect_cpf,
            self.COLLECT_BIRTH_STATE: self._collect_birth,
            self.COLLECT_CITY_STATE: self._collect_city,
        }

        handler = handlers.get(state)

        if not handler:
            logger.warning(
                "Estado de cadastro desconhecido: phone=%s state=%s",
                phone,
                state,
            )
            return

        await handler(
            phone=phone,
            text=text.strip(),
            session=session,
        )

    async def _collect_name(
        self,
        phone: str,
        text: str,
        session: dict[str, Any],
    ) -> None:
        name = self._normalize_spaces(text)

        if not self._is_valid_name(name):
            await self.whatsapp.send_text(
                phone,
                "Não consegui validar o nome informado.\n\n"
                "Digite seu nome completo, com pelo menos nome e sobrenome.\n\n"
                "Exemplo: Maria da Silva",
            )
            return

        data = self._get_session_data(session)
        data["name"] = name

        await self.sessions.set(
            phone=phone,
            state=self.COLLECT_CPF_STATE,
            topic=session.get("topic"),
            data=data,
        )

        first_name = name.split()[0]

        await self.whatsapp.send_text(
            phone,
            f"Obrigado, {first_name}.\n\n"
            "Agora informe seu CPF.\n\n"
            "Você pode digitar com ou sem pontos e traço.",
        )

    async def _collect_cpf(
        self,
        phone: str,
        text: str,
        session: dict[str, Any],
    ) -> None:
        cpf_digits = self._only_digits(text)

        if not self._is_valid_cpf(cpf_digits):
            await self.whatsapp.send_text(
                phone,
                "O CPF informado não parece válido.\n\n"
                "Confira os 11 números e tente novamente.\n\n"
                "Exemplo: 123.456.789-00",
            )
            return

        formatted_cpf = self._format_cpf(cpf_digits)

        data = self._get_session_data(session)
        data["cpf"] = formatted_cpf

        await self.sessions.set(
            phone=phone,
            state=self.COLLECT_BIRTH_STATE,
            topic=session.get("topic"),
            data=data,
        )

        await self.whatsapp.send_text(
            phone,
            "Informe sua data de nascimento.\n\n"
            "Use o formato DD/MM/AAAA.\n\n"
            "Exemplo: 15/08/1990",
        )

    async def _collect_birth(
        self,
        phone: str,
        text: str,
        session: dict[str, Any],
    ) -> None:
        birth_date = self._parse_birth_date(text)

        if birth_date is None:
            await self.whatsapp.send_text(
                phone,
                "A data informada não parece válida.\n\n"
                "Digite uma data real no formato DD/MM/AAAA.\n\n"
                "Exemplo: 15/08/1990",
            )
            return

        if birth_date > date.today():
            await self.whatsapp.send_text(
                phone,
                "A data de nascimento não pode estar no futuro.\n\n"
                "Digite novamente no formato DD/MM/AAAA.",
            )
            return

        age = self._calculate_age(birth_date)

        if age > 120:
            await self.whatsapp.send_text(
                phone,
                "A data informada resultou em uma idade acima de 120 anos.\n\n"
                "Confira a data e digite novamente no formato DD/MM/AAAA.",
            )
            return

        formatted_birth_date = birth_date.strftime("%d/%m/%Y")

        data = self._get_session_data(session)
        data["birth_date"] = formatted_birth_date

        await self.sessions.set(
            phone=phone,
            state=self.COLLECT_CITY_STATE,
            topic=session.get("topic"),
            data=data,
        )

        await self.whatsapp.send_text(
            phone,
            "Para finalizar o cadastro, informe sua cidade e estado.\n\n"
            "Exemplo: Manaus/AM",
        )

    async def _collect_city(
        self,
        phone: str,
        text: str,
        session: dict[str, Any],
    ) -> None:
        city = self._normalize_spaces(text)

        if not self._is_valid_city(city):
            await self.whatsapp.send_text(
                phone,
                "Não consegui identificar corretamente a cidade e o estado.\n\n"
                "Informe no formato Cidade/UF.\n\n"
                "Exemplo: Manaus/AM",
            )
            return

        formatted_city = self._format_city(city)

        data = self._get_session_data(session)
        data["city"] = formatted_city

        topic = session.get("topic")

        await self.sessions.set(
            phone=phone,
            state=self.WAITING_HUMAN_STATE,
            topic=topic,
            data=data,
        )

        await self._finish(
            phone=phone,
            topic=topic,
            data=data,
        )

    async def _finish(
        self,
        phone: str,
        topic: str | None,
        data: dict[str, Any],
    ) -> None:
        """
        Envia o resumo e encaminha o cliente ao atendimento humano.
        """

        topic_label = self.TOPIC_LABELS.get(
            topic or "",
            topic or "Não informado",
        )

        await self.whatsapp.send_text(
            phone,
            "✅ Cadastro concluído.\n\n"
            "Confira os dados informados:\n\n"
            f"Assunto: {topic_label}\n"
            f"Nome: {data.get('name', 'Não informado')}\n"
            f"CPF: {data.get('cpf', 'Não informado')}\n"
            f"Nascimento: {data.get('birth_date', 'Não informado')}\n"
            f"Cidade/UF: {data.get('city', 'Não informado')}\n\n"
            "Seu atendimento foi encaminhado para nossa equipe.\n"
            "Em breve um de nossos atendentes responderá por aqui.",
        )

        logger.info(
            "Cadastro concluído: phone=%s topic=%s",
            phone,
            topic,
        )

    # ==================================================
    # Validações
    # ==================================================

    @classmethod
    def _is_valid_name(
        cls,
        name: str,
    ) -> bool:
        """
        Exige pelo menos nome e sobrenome.

        Aceita letras, espaços, apóstrofos e hífens.
        """

        if len(name) < 5 or len(name) > 120:
            return False

        parts = name.split()

        if len(parts) < 2:
            return False

        valid_part_pattern = re.compile(
            r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$"
        )

        return all(
            valid_part_pattern.fullmatch(part) is not None
            for part in parts
        )

    @staticmethod
    def _is_valid_cpf(
        cpf: str,
    ) -> bool:
        """
        Valida os dois dígitos verificadores do CPF.
        """

        if len(cpf) != 11:
            return False

        if not cpf.isdigit():
            return False

        if cpf == cpf[0] * 11:
            return False

        first_total = sum(
            int(cpf[index]) * (10 - index)
            for index in range(9)
        )

        first_digit = (first_total * 10) % 11

        if first_digit == 10:
            first_digit = 0

        if first_digit != int(cpf[9]):
            return False

        second_total = sum(
            int(cpf[index]) * (11 - index)
            for index in range(10)
        )

        second_digit = (second_total * 10) % 11

        if second_digit == 10:
            second_digit = 0

        return second_digit == int(cpf[10])

    @staticmethod
    def _parse_birth_date(
        value: str,
    ) -> date | None:
        """
        Converte estritamente uma data no formato DD/MM/AAAA.
        """

        try:
            parsed = datetime.strptime(
                value.strip(),
                "%d/%m/%Y",
            )

            return parsed.date()

        except (TypeError, ValueError):
            return None

    @staticmethod
    def _calculate_age(
        birth_date: date,
    ) -> int:
        today = date.today()

        return (
            today.year
            - birth_date.year
            - (
                (today.month, today.day)
                < (birth_date.month, birth_date.day)
            )
        )

    @classmethod
    def _is_valid_city(
        cls,
        value: str,
    ) -> bool:
        """
        Valida o formato Cidade/UF.
        """

        if len(value) < 4 or len(value) > 100:
            return False

        if "/" not in value:
            return False

        city, state = value.rsplit("/", maxsplit=1)

        city = cls._normalize_spaces(city)
        state = state.strip()

        if len(city) < 2:
            return False

        if not re.fullmatch(r"[A-Za-z]{2}", state):
            return False

        city_pattern = re.compile(
            r"^[A-Za-zÀ-ÖØ-öø-ÿ]+"
            r"(?:[\s'-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$"
        )

        return city_pattern.fullmatch(city) is not None

    @classmethod
    def _format_city(
        cls,
        value: str,
    ) -> str:
        city, state = value.rsplit("/", maxsplit=1)

        return (
            f"{cls._normalize_spaces(city)}/"
            f"{state.strip().upper()}"
        )

    @staticmethod
    def _format_cpf(
        cpf: str,
    ) -> str:
        return (
            f"{cpf[:3]}."
            f"{cpf[3:6]}."
            f"{cpf[6:9]}-"
            f"{cpf[9:]}"
        )

    @staticmethod
    def _only_digits(
        value: str,
    ) -> str:
        return re.sub(r"\D", "", value)

    @staticmethod
    def _normalize_spaces(
        value: str,
    ) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _get_session_data(
        session: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Retorna uma cópia dos dados atuais da sessão.
        """

        return dict(session.get("data") or {})