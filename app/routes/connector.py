import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.conversation import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhook/connector",
    tags=["Connector"],
)

conversation = ConversationService()


class ConnectorMessage(BaseModel):
    sender: str = Field(alias="from")
    text: str


@router.post("")
async def receive_message(
    payload: ConnectorMessage,
    authorization: str | None = Header(default=None),
):
    expected = f"Bearer {settings.CONNECTOR_SECRET}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    sender = payload.sender.strip()
    text = payload.text.strip()

    if not sender:
        raise HTTPException(
            status_code=422,
            detail="Campo 'from' não pode estar vazio.",
        )

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Campo 'text' não pode estar vazio.",
        )

    logger.info(
        "Mensagem recebida do connector: from=%s text=%s",
        sender,
        text,
    )

    try:
        await conversation.process_connector(
            {
                "from": sender,
                "text": text,
            },
        )

    except Exception:
        logger.exception(
            "Erro ao processar mensagem recebida do connector.",
        )

        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar mensagem.",
        )

    return {
        "status": "received",
    }