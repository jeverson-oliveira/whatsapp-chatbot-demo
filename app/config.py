import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __init__(self) -> None:
        self.WHATSAPP_PROVIDER = os.getenv(
            "WHATSAPP_PROVIDER",
            "baileys",
        )

        self.connector_url = os.getenv(
            "CONNECTOR_URL",
            "http://localhost:3300",
        )

        self.CONNECTOR_URL = self.connector_url

        self.connector_secret = os.getenv(
            "CONNECTOR_SECRET",
            "",
        )

        self.CONNECTOR_SECRET = self.connector_secret 

        self.SESSIONS_DB_PATH = os.getenv(
            "SESSIONS_DB_PATH",
            "sessions.db",
        )

        self.SESSION_TIMEOUT_SECONDS = int( os.getenv(
            "SESSION_TIMEOUT_SECONDS",
            "1800",
        ) )


        self.meta_api_version = os.getenv(
            "META_API_VERSION",
            "v25.0",
        )

        self.phone_number_id = os.getenv(
            "PHONE_NUMBER_ID",
            "",
        )

        self.whatsapp_token = os.getenv(
            "WHATSAPP_TOKEN",
            "",
        )

        self.verify_token = os.getenv(
            "VERIFY_TOKEN",
            "",
        )

        self.human_attendant = os.getenv(
            "HUMAN_ATTENDANT",
            os.getenv("HUMAN_ATTENDANT_NAME", "Equipe de Atendimento"),
        )
        self.HUMAN_ATTENDANT_NAME = self.human_attendant

        # --- White Label ---
        self.APP_NAME = os.getenv("APP_NAME", "WhatsApp Chatbot")
        self.APP_VERSION = os.getenv("APP_VERSION", "1.1.0")

        self.BUSINESS_NAME = os.getenv(
            "BUSINESS_NAME",
            "Sua Empresa",
        )
        self.BUSINESS_DESCRIPTION = os.getenv(
            "BUSINESS_DESCRIPTION",
            "Atendimento automatizado via WhatsApp",
        )
        self.BUSINESS_FOOTER = os.getenv(
            "BUSINESS_FOOTER",
            "Seus dados serão utilizados exclusivamente para atendimento, conforme LGPD.",
        )
        self.WELCOME_TITLE = os.getenv("WELCOME_TITLE", "Bem-vindo(a)!")
        self.WELCOME_BODY = os.getenv(
            "WELCOME_BODY",
            "Olá! Seja bem-vindo(a). Escolha uma das opções abaixo para continuar.",
        )

settings = Settings()