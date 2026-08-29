"""
Menus genéricos white-label.

Edite este arquivo para customizar por cliente/marca
ou carregue via banco/CMS. As chaves abaixo são apenas
exemplos neutros e podem ser trocadas sem alterar o fluxo.
"""
import os

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Sua Empresa")
WELCOME_TITLE = os.getenv("WELCOME_TITLE", "Bem-vindo(a)!")
WELCOME_BODY = os.getenv(
    "WELCOME_BODY",
    "Olá! Seja bem-vindo(a). Escolha uma das opções abaixo para continuar.",
)
BUSINESS_FOOTER = os.getenv(
    "BUSINESS_FOOTER",
    "Seus dados serão utilizados exclusivamente para atendimento, conforme LGPD.",
)

MENUS = {

    "main": {
        "type": "list",

        "title": BUSINESS_NAME,

        "body": (
            f"{BUSINESS_NAME}\n\n"
            f"{WELCOME_TITLE}\n\n"
            f"{WELCOME_BODY}\n\n"
            f"{BUSINESS_FOOTER}\n\n"
            "Escolha o assunto do atendimento:"
        ),

        "button": "Ver opções",

        "rows": [
            {
                "id": "produtos_servicos",
                "title": "Produtos e Serviços"
            },
            {
                "id": "suporte_tecnico",
                "title": "Suporte Técnico"
            },
            {
                "id": "financeiro",
                "title": "Financeiro"
            },
            {
                "id": "informacoes",
                "title": "Informações Gerais"
            },
            {
                "id": "falar_atendente",
                "title": "Falar com atendente"
            },
            {
                "id": "outro_assunto",
                "title": "Outro assunto"
            }
        ]
    },

    "produtos_servicos": {
        "type": "human",
        "text": (
            "Você selecionou: Produtos e Serviços.\n\n"
            "Seu atendimento será direcionado para nossa equipe responsável, "
            "que dará continuidade por aqui."
        )
    },

    "suporte_tecnico": {
        "type": "human",
        "text": (
            "Você selecionou: Suporte Técnico.\n\n"
            "Seu atendimento será direcionado para análise humana. "
            "Aguarde o retorno da equipe."
        )
    },

    "financeiro": {
        "type": "human",
        "text": (
            "Você selecionou: Financeiro.\n\n"
            "Seu atendimento será direcionado para análise humana. "
            "Aguarde o retorno da equipe."
        )
    },

    "informacoes": {
        "type": "human",
        "text": (
            "Você selecionou: Informações Gerais.\n\n"
            "Seu atendimento será direcionado para análise humana. "
            "Aguarde o retorno da equipe."
        )
    },

    "falar_atendente": {
        "type": "human",
        "text": (
            "Você solicitou falar com um atendente.\n\n"
            "Seu atendimento será direcionado para análise humana. "
            "Aguarde o retorno da equipe."
        )
    },

    "outro_assunto": {
        "type": "human",
        "text": (
            "Seu assunto será encaminhado para análise humana.\n\n"
            "Aguarde o retorno da equipe de atendimento."
        )
    },

    # Alias genérico compatível com fluxos antigos
    "especialista": {
        "type": "human",
        "text": (
            "Seu atendimento será direcionado para análise humana.\n\n"
            "Aguarde o retorno da equipe."
        )
    }

}
