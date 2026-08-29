# app/routes/webhook.py

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Request,
    HTTPException,
)
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.services.conversation import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"]
)

conversation = ConversationService()


@router.get("")
async def verify_webhook(
    request: Request
):
    """
    Verificação do webhook Meta (GET com hub.mode, hub.verify_token, hub.challenge).
    Retorna PlainTextResponse com o challenge conforme spec Meta.
    """
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == settings.verify_token
        and challenge is not None
    ):
        logger.info("Webhook verificado com sucesso (challenge=%s)", challenge)
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning(
        "Falha na verificação do webhook: mode=%s token_match=%s",
        mode,
        token == settings.verify_token,
    )
    raise HTTPException(
        status_code=403,
        detail="Token inválido"
    )


@router.post("")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
):

    body = await request.json()

    logger.info("Webhook recebido: %s", body)

    # Responde 200 imediatamente e processa em background.
    # Isso evita que o Meta considere o webhook "travado" (e reenvie o
    # mesmo evento) enquanto aguardamos a chamada à Graph API terminar.
    background_tasks.add_task(conversation.process, body)

    return {
        "status": "received"
    }
