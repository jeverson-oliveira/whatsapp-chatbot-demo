import logging
from typing import Any

from app.services.menu import MenuService
from app.services.registration import RegistrationFlow
from app.services.session_store import SessionStore
from app.services.whatsapp import WhatsAppService


logger = logging.getLogger(__name__)


class ConversationService:
    """
    Orquestra o fluxo da conversa para Meta Cloud API e Baileys.

    Responsabilidades:
    - receber e normalizar mensagens;
    - exibir menus;
    - identificar o estado da sessão;
    - delegar o cadastro para RegistrationFlow;
    - controlar o encaminhamento ao atendimento humano.
    """

    MAIN_MENU_STATE = "menu"

    INITIAL_COMMANDS = {
        "",
        "oi",
        "olá",
        "ola",
        "menu",
        "início",
        "inicio",
        "começar",
        "comecar",
    }

    TEXT_OPTIONS = {
        "1": "produtos_servicos",
        "2": "suporte_tecnico",
        "3": "financeiro",
        "4": "informacoes",
        "5": "falar_atendente",
        "6": "outro_assunto",
    }

    def __init__(self) -> None:
        self.whatsapp = WhatsAppService()
        self.menu = MenuService(self.whatsapp)
        self.sessions = SessionStore()

        self.registration = RegistrationFlow(
            whatsapp=self.whatsapp,
            sessions=self.sessions,
        )

    # ==================================================
    # Meta Cloud API
    # ==================================================

    async def process(
        self,
        payload: dict[str, Any],
    ) -> None:
        """
        Processa o payload original recebido da Meta Cloud API.
        Compatível com spec v25.0:
          object: whatsapp_business_account
          entry[0].changes[0].value.messages[], contacts[], metadata, statuses[]
        """
        try:
            if payload.get("object") != "whatsapp_business_account":
                logger.debug(
                    "Payload ignorado por não ser do WhatsApp Business: %s",
                    payload.get("object"),
                )
                return

            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    # Loga statuses (entregue/lido) sem processar
                    if value.get("statuses"):
                        logger.info("Status update ignorado: %s", value.get("statuses"))

                    # Marca contatos/metadata para debug
                    contacts = value.get("contacts", [])
                    metadata = value.get("metadata", {})
                    if contacts:
                        logger.debug("Contacts: %s Metadata: %s", contacts, metadata)

                    for message in value.get("messages", []):
                        # tenta marcar como lida antes de processar (best-effort)
                        msg_id = message.get("id")
                        if msg_id:
                            try:
                                await self.whatsapp.mark_as_read(msg_id)
                            except Exception:
                                logger.debug("Falha ao marcar como lida %s", msg_id, exc_info=True)

                        await self.handle_message(message)

        except Exception:
            logger.exception(
                "Falha ao processar payload da Meta: %s",
                payload,
            )

    # ==================================================
    # Baileys Connector
    # ==================================================

    async def process_connector(
        self,
        payload: dict[str, Any],
    ) -> None:
        """
        Processa o formato simplificado enviado pelo Baileys Connector.

        Exemplo:

        {
            "from": "225430418272346@lid",
            "text": "Oi"
        }
        """

        phone = payload.get("from")
        text = payload.get("text")

        if not isinstance(phone, str) or not phone.strip():
            raise ValueError(
                "Payload do connector sem o campo 'from'."
            )

        if not isinstance(text, str) or not text.strip():
            logger.warning(
                "Mensagem vazia recebida do connector: %s",
                payload,
            )
            return

        message = {
            "from": phone.strip(),
            "type": "text",
            "text": {
                "body": text.strip(),
            },
        }

        logger.info(
            "Processando mensagem do connector: from=%s text=%s",
            phone,
            text,
        )

        await self.handle_message(message)

    # ==================================================
    # Fluxo comum
    # ==================================================

    async def handle_message(
        self,
        message: dict[str, Any],
    ) -> None:
        """
        Direciona mensagens de texto ou interativas para seus handlers.
        """

        phone = message.get("from")
        message_type = message.get("type")

        if not isinstance(phone, str) or not phone.strip():
            logger.warning(
                "Mensagem sem campo 'from': %s",
                message,
            )
            return

        phone = phone.strip()

        try:
            if message_type == "interactive":
                await self.handle_interactive(
                    phone,
                    message,
                )
                return

            text = self._extract_text(message)

            await self.handle_text(
                phone,
                text,
            )

        except Exception:
            logger.exception(
                "Falha ao tratar mensagem de %s: %s",
                phone,
                message,
            )

            await self._safe_notify_error(phone)

    def _extract_text(
        self,
        message: dict[str, Any],
    ) -> str:
        """
        Extrai texto de mensagens recebidas da Meta ou do connector.
        """

        text_data = message.get("text")

        if isinstance(text_data, dict):
            return str(
                text_data.get("body", "")
            ).strip()

        if isinstance(text_data, str):
            return text_data.strip()

        return ""

    # ==================================================
    # Mensagens de texto
    # ==================================================

    async def handle_text(
        self,
        phone: str,
        text: str = "",
    ) -> None:
        """
        Trata mensagens textuais, opções numéricas e etapas do cadastro.
        """

        clean_text = text.strip()
        normalized_text = clean_text.lower()

        session = await self.sessions.get(phone)

        logger.info(
            "Tratando texto de %s. Texto=%s Estado=%s",
            phone,
            normalized_text,
            session.get("state") if session else None,
        )

        # O comando MENU reinicia o fluxo em qualquer etapa.
        if normalized_text in self.INITIAL_COMMANDS:
            await self.sessions.clear(phone)
            await self._show_main_menu(phone)
            return

        # Sem sessão válida, inicia novamente pelo menu principal.
        if not session:
            await self._show_main_menu(phone)
            return

        state = session.get("state")

        # O RegistrationFlow controla nome, CPF, nascimento e cidade.
        if self.registration.handles(state):
            await self.registration.handle(
                phone=phone,
                text=clean_text,
                session=session,
            )
            return

        # Depois do cadastro, as mensagens aguardam o humano.
        if self._is_waiting_human(session):
            await self._notify_waiting_human(phone)
            return

        selected = self.TEXT_OPTIONS.get(normalized_text)

        if not selected:
            await self._notify_invalid_option(phone)
            return

        await self._process_selection(
            phone=phone,
            selected=selected,
        )

    # ==================================================
    # Mensagens interativas
    # ==================================================

    async def handle_interactive(
        self,
        phone: str,
        message: dict[str, Any],
    ) -> None:
        """
        Trata respostas de listas e botões da Meta Cloud API.
        """

        interactive = message.get("interactive", {})

        selected = (
            interactive
            .get("list_reply", {})
            .get("id")
            or interactive
            .get("button_reply", {})
            .get("id")
        )

        if not selected:
            logger.warning(
                "Interação sem ID selecionado: %s",
                message,
            )
            return

        selected = str(selected)

        logger.info(
            "Opção interativa selecionada por %s: %s",
            phone,
            selected,
        )

        await self._process_selection(
            phone=phone,
            selected=selected,
        )

    # ==================================================
    # Seleções e estados
    # ==================================================

    async def _process_selection(
        self,
        phone: str,
        selected: str,
    ) -> None:
        """
        Processa uma opção selecionada no menu.

        Menus do tipo list exibem um submenu.
        Opções finais iniciam o cadastro.
        """

        menu_type = self.menu.get_type(selected)

        if not menu_type:
            logger.warning(
                "Menu não encontrado: phone=%s selected=%s",
                phone,
                selected,
            )

            await self._notify_invalid_option(phone)
            return

        logger.info(
            "Processando seleção: phone=%s selected=%s type=%s",
            phone,
            selected,
            menu_type,
        )

        await self.menu.show(
            phone,
            selected,
        )

        if menu_type == "list":
            await self.sessions.set(
                phone=phone,
                state=self.MAIN_MENU_STATE,
            )
            return

        await self.registration.start(
            phone=phone,
            topic=selected,
        )

    async def _show_main_menu(
        self,
        phone: str,
    ) -> None:
        """
        Exibe o menu principal e registra o estado da conversa.
        """

        logger.info(
            "Exibindo menu principal para %s",
            phone,
        )

        await self.menu.show(
            phone,
            "main",
        )

        await self.sessions.set(
            phone=phone,
            state=self.MAIN_MENU_STATE,
        )

    # ==================================================
    # Respostas auxiliares
    # ==================================================

    def _is_waiting_human(
        self,
        session: dict[str, Any] | None,
    ) -> bool:
        return bool(
            session
            and session.get("state")
            == self.registration.WAITING_HUMAN_STATE
        )

    async def _notify_waiting_human(
        self,
        phone: str,
    ) -> None:
        await self.whatsapp.send_text(
            phone,
            "Você já está na fila de atendimento. "
            "Em breve um de nossos atendentes "
            "responderá por aqui mesmo.\n\n"
            "Para iniciar um novo atendimento, envie MENU.",
        )

    async def _notify_invalid_option(
        self,
        phone: str,
    ) -> None:
        await self.whatsapp.send_text(
            phone,
            "Opção inválida.\n\n"
            "Digite um número correspondente a uma das opções "
            "ou envie MENU para visualizar o menu principal.",
        )

    async def _safe_notify_error(
        self,
        phone: str,
    ) -> None:
        """
        Tenta informar o usuário sem ocultar o erro original.
        """

        try:
            await self.whatsapp.send_text(
                phone,
                "Desculpe, tivemos um problema ao processar sua mensagem. "
                "Tente novamente em instantes.",
            )

        except Exception:
            logger.exception(
                "Falha também ao notificar erro para %s",
                phone,
            )
