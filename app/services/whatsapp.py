import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Abstrai o envio de mensagens para os dois providers suportados:

    - meta:   WhatsApp Cloud API (Graph API)
    - baileys: conector Baileys via HTTP (CONNECTOR_URL)

    Compatível com white-label: nenhuma marca é hardcoded, todos os
    tokens/ids vêm de settings (.env).
    """

    def __init__(self) -> None:
        self.provider = settings.WHATSAPP_PROVIDER.lower()

        # Baileys
        self.connector_url = settings.connector_url.rstrip("/")
        self.connector_secret = settings.connector_secret

        # Meta
        self.meta_version = settings.meta_api_version
        self.phone_number_id = settings.phone_number_id
        self.whatsapp_token = settings.whatsapp_token

        self.graph_base = "https://graph.facebook.com"

    # ============================================================
    # Helpers
    # ============================================================

    def _is_meta(self) -> bool:
        return self.provider == "meta"

    def _meta_url(self) -> str:
        return f"{self.graph_base}/{self.meta_version}/{self.phone_number_id}/messages"

    def _meta_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json",
        }

    def _connector_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.connector_secret}",
            "Content-Type": "application/json",
        }

    # ============================================================
    # Texto simples
    # ============================================================

    async def send_text(
        self,
        to: str,
        text: str,
    ) -> None:
        """
        Envia texto simples, compatível com ambos os providers.
        Para Meta, usa endpoint /messages com type=text.
        """
        if self._is_meta():
            await self._send_meta_text(to, text)
        else:
            await self._send_connector_text(to, text)

    async def _send_meta_text(
        self,
        to: str,
        text: str,
    ) -> None:
        if not self.phone_number_id or not self.whatsapp_token:
            logger.error(
                "Meta não configurado: PHONE_NUMBER_ID ou WHATSAPP_TOKEN vazio. "
                "Defina no .env para WHATSAPP_PROVIDER=meta."
            )
            return

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text[:4096],  # limite Meta
            },
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    self._meta_url(),
                    json=payload,
                    headers=self._meta_headers(),
                )

                if response.is_error:
                    logger.error(
                        "Meta Graph API erro para %s: status=%s body=%s",
                        to,
                        response.status_code,
                        response.text,
                    )
                response.raise_for_status()
                logger.info("Mensagem Meta enviada para %s", to)

        except httpx.HTTPError:
            logger.exception("Falha ao enviar texto via Meta para %s", to)
            raise

    async def _send_connector_text(
        self,
        to: str,
        text: str,
    ) -> None:
        payload = {"to": to, "text": text}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self.connector_url}/send",
                    json=payload,
                    headers=self._connector_headers(),
                )

                if response.is_error:
                    logger.error(
                        "Connector erro para %s: status=%s body=%s",
                        to,
                        response.status_code,
                        response.text,
                    )
                response.raise_for_status()
                logger.info("Mensagem connector enviada para %s", to)

        except httpx.HTTPError:
            logger.exception("Falha ao enviar via connector para %s", to)
            raise

    # ============================================================
    # Listas interativas (Meta)
    # ============================================================

    async def send_interactive_list(
        self,
        to: str,
        body: str,
        button: str,
        rows: list[dict],
        header_title: str | None = None,
        footer_text: str | None = None,
    ) -> None:
        """
        Envia lista interativa Meta. Para Baileys faz fallback para texto numerado.

        Meta limites:
        - body 1024 chars
        - button 20 chars
        - header 60 chars
        - footer 60 chars
        - rows até 10, cada title 24 chars, description opcional 72
        """
        if not self._is_meta():
            # fallback Baileys: texto numerado (mantido em MenuService também)
            fallback = body + "\n\n"
            for i, r in enumerate(rows, 1):
                fallback += f"{i} - {r.get('title','Opção')}\n"
            fallback += "\nDigite o número da opção desejada."
            await self.send_text(to, fallback)
            return

        if not self.phone_number_id or not self.whatsapp_token:
            logger.error("Meta não configurado para lista interativa")
            # fallback para texto
            await self._send_meta_text(to, body)
            return

        # Trunca conforme spec
        body = body[:1024]
        button = (button or "Ver opções")[:20]

        # Monta rows no formato Meta
        meta_rows = []
        for r in rows[:10]:
            title = str(r.get("title", "Opção"))[:24]
            row_id = str(r.get("id", title.lower().replace(" ", "_")))[:200]
            desc = str(r.get("description", ""))[:72]
            row = {"id": row_id, "title": title}
            if desc:
                row["description"] = desc
            meta_rows.append(row)

        interactive: dict = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button,
                "sections": [
                    {
                        "title": (header_title or "Opções")[:24],
                        "rows": meta_rows,
                    }
                ],
            },
        }

        if header_title:
            # header opcional 60 chars
            interactive["header"] = {"type": "text", "text": header_title[:60]}

        if footer_text:
            interactive["footer"] = {"text": footer_text[:60]}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    self._meta_url(),
                    json=payload,
                    headers=self._meta_headers(),
                )
                if response.is_error:
                    logger.error(
                        "Meta lista erro para %s: status=%s body=%s req=%s",
                        to,
                        response.status_code,
                        response.text,
                        payload,
                    )
                    # fallback para texto se lista falhar (ex: template não aprovado)
                    await self._send_meta_text(to, body + "\n\nResponda com o número da opção.")
                else:
                    logger.info("Lista Meta enviada para %s (%d rows)", to, len(meta_rows))
                response.raise_for_status()

        except httpx.HTTPError:
            logger.exception("Falha ao enviar lista Meta para %s", to)
            raise

    # ============================================================
    # Buttons (até 3, opcional)
    # ============================================================

    async def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[dict],
    ) -> None:
        """
        Envia botões de resposta rápida (Meta). Fallback para texto.
        buttons: [{"id":"...","title":"..."}] até 3, title 20 chars
        """
        if not self._is_meta():
            await self.send_text(to, body)
            return

        if not self.phone_number_id or not self.whatsapp_token:
            await self._send_meta_text(to, body)
            return

        meta_buttons = []
        for b in buttons[:3]:
            meta_buttons.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": str(b.get("id"))[:256],
                        "title": str(b.get("title"))[:20],
                    },
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {"buttons": meta_buttons},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    self._meta_url(),
                    json=payload,
                    headers=self._meta_headers(),
                )
                if response.is_error:
                    logger.error("Meta buttons erro: %s %s", response.status_code, response.text)
                    await self._send_meta_text(to, body)
                response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Falha ao enviar buttons Meta para %s", to)
            raise

    # ============================================================
    # Mark as read (opcional, Meta)
    # ============================================================

    async def mark_as_read(
        self,
        message_id: str,
    ) -> None:
        if not self._is_meta() or not message_id:
            return
        if not self.phone_number_id or not self.whatsapp_token:
            return

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    self._meta_url(),
                    json=payload,
                    headers=self._meta_headers(),
                )
        except Exception:
            logger.debug("Falha ao marcar como lida %s", message_id, exc_info=True)
