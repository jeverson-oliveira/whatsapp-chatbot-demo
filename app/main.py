import logging

from fastapi import FastAPI

from app.config import settings
from app.routes import connector
from app.routes import webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

# Compatível com Meta: registra ambos os routers sempre.
# O envio (WhatsAppService) ainda respeita WHATSAPP_PROVIDER,
# mas o webhook fica disponível para testes/switch sem restart.
app.include_router(webhook.router)
app.include_router(connector.router)


@app.get("/")
async def root():
    return {
        "application": settings.APP_NAME,
        "business": settings.BUSINESS_NAME,
        "provider": settings.WHATSAPP_PROVIDER,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": settings.WHATSAPP_PROVIDER,
    }