# app/routes/webhook.py

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Request,
    HTTPException,
)

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

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == settings.VERIFY_TOKEN
        and challenge is not None
    ):
        return int(challenge)

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