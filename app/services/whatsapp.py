import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class WhatsAppService:

    def __init__(self) -> None:
        self.base_url = settings.connector_url.rstrip("/")
        self.secret = settings.connector_secret

    async def send_text(
        self,
        to: str,
        text: str,
    ) -> None:

        payload = {
            "to": to,
            "text": text,
        }

        headers = {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=20,
            ) as client:

                response = await client.post(
                    f"{self.base_url}/send",
                    json=payload,
                    headers=headers,
                )

                if response.is_error:
                    logger.error(
                        "Connector retornou erro HTTP para %s: "
                        "status=%s body=%s",
                        to,
                        response.status_code,
                        response.text,
                    )

                response.raise_for_status()

                logger.info(
                    "Mensagem enviada pelo connector para %s",
                    to,
                )

        except httpx.HTTPError:
            logger.exception(
                "Falha ao enviar mensagem pelo connector para %s",
                to,
            )
            raise