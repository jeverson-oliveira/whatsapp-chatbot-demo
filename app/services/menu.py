import logging

from app.config import settings
from app.data.menus import MENUS
from app.services.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)


class MenuService:

    def __init__(
        self,
        whatsapp: WhatsAppService,
    ) -> None:
        self.whatsapp = whatsapp

    def get_type(
        self,
        menu_id: str,
    ) -> str | None:
        menu = MENUS.get(menu_id)

        if not menu:
            return None

        return menu.get("type")

    async def show(
        self,
        phone: str,
        menu_id: str,
    ) -> None:
        menu = MENUS.get(menu_id)

        if not menu:
            logger.warning(
                "Menu não encontrado: %s",
                menu_id,
            )

            await self.whatsapp.send_text(
                to=phone,
                text="Opção não encontrada.",
            )
            return

        menu_type = menu.get("type")

        logger.info(
            "Enviando menu %s para %s. Tipo=%s",
            menu_id,
            phone,
            menu_type,
        )

        if menu_type == "list":
            await self._send_text_list(
                phone,
                menu,
            )
            return

        if menu_type == "human":
            await self.whatsapp.send_text(
                to=phone,
                text=menu.get(
                    "text",
                    "Encaminhando seu atendimento para nossa equipe.",
                ),
            )
            return

        logger.warning(
            "Tipo de menu não suportado: menu=%s type=%s",
            menu_id,
            menu_type,
        )

        await self.whatsapp.send_text(
            to=phone,
            text="Não foi possível exibir esta opção.",
        )

    async def _send_text_list(
        self,
        phone: str,
        menu: dict,
    ) -> None:
        rows = menu.get("rows", [])

        options = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            title = row.get(
                "title",
                "Opção",
            )

            options.append(
                f"{index} - {title}"
            )

        body = menu.get(
            "body",
            "Selecione uma opção:",
        )

        text = (
            f"{body}\n\n"
            + "\n".join(options)
            + "\n\nDigite o número da opção desejada."
        )

        await self.whatsapp.send_text(
            to=phone,
            text=text,
        )

    async def send_human(
        self,
        phone: str,
    ) -> None:
        attendant = getattr(settings, "HUMAN_ATTENDANT_NAME", "Equipe de Atendimento")
        text = (
            "Obrigado pelo contato.\n\n"
            "Seu atendimento será direcionado para "
            f"{attendant}, que continuará a conversa por aqui."
        )

        await self.whatsapp.send_text(
            to=phone,
            text=text,
        )