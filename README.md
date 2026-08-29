# WhatsApp Chatbot — White Label

> Plataforma white-label de atendimento automatizado via WhatsApp, compatível com **Meta Cloud API** (Graph API) e **Baileys Connector**. Toda a identidade — marca, menus, mensagens e fluxo — é configurável por ambiente, sem hardcode.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688)](https://fastapi.tiangolo.com)
[![Meta API v25.0](https://img.shields.io/badge/Meta%20API-v25.0-1877F2)](https://developers.facebook.com/docs/whatsapp/cloud-api)
[![License: White-Label](https://img.shields.io/badge/license-white--label-lightgrey)](#licença)

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Funcionalidades](#funcionalidades)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [White Label](#white-label)
- [Integração Meta Cloud API](#integração-meta-cloud-api)
- [Endpoints](#endpoints)
- [Fluxo de Conversa](#fluxo-de-conversa)
- [Sessão e Persistência](#sessão-e-persistência)
- [Docker](#docker)
- [Testes](#testes)
- [Deploy](#deploy)
- [Troubleshooting](#troubleshooting)
- [Contribuição](#contribuição)
- [Licença](#licença)

---

## Visão Geral

Este projeto entrega um **chatbot de WhatsApp pronto para produção** com dois providers intercambiáveis:

- **Meta** — WhatsApp Cloud API (recomendado para números oficiais, verificação via `VERIFY_TOKEN` e envio pela Graph API).
- **Baileys** — conector HTTP auto-hospedado (ideal para desenvolvimento e números não oficiais).

O repositório foi convertido para **white-label**: basta trocar `.env` e `app/data/menus.py` para atender outro cliente, sem alterar lógica de negócio. O histórico anterior foi limpo; o commit inicial é `feat: initial commit - white-label chatbot template`.

---

## Arquitetura

```
WhatsApp User
     │
     ├─► Meta Cloud ──► POST /webhook ──┐
     └─► Baileys ────► POST /webhook/connector ─┤
                                                    │
                                          ConversationService
                                          ├─ SessionStore (SQLite)
                                          ├─ MenuService ──► WhatsAppService
                                          └─ RegistrationFlow ──► WhatsAppService
                                                    │
                                          Graph API / Connector /send
```

- **FastAPI** expõe webhooks e health checks. Ambos os routers são registrados simultaneamente — a escolha do provider para *envio* é feita em tempo de execução via `WHATSAPP_PROVIDER`.
- **ConversationService** orquestra estado, comandos (`oi`, `menu`, `início`), opções numéricas (`1`–`6`) e callbacks interativos (`list_reply` / `button_reply`).
- **WhatsAppService** abstrai o transporte: Graph API para Meta e `POST {CONNECTOR_URL}/send` para Baileys, com fallback automático.

---

## Tecnologias

| Camada | Stack |
|--------|-------|
| API | FastAPI 0.116, Uvicorn 0.35, Pydantic |
| WhatsApp | httpx 0.28, Meta Graph API v25.0, Baileys Connector |
| Persistência | SQLite + asyncio.to_thread, SessionStore com TTL |
| Config | python-dotenv 1.1, Settings env-driven |
| Infra | Docker, Docker Compose, Python 3.13 |

---

## Funcionalidades

- **Menu principal genérico** com 6 opções neutras (`produtos_servicos`, `suporte_tecnico`, `financeiro`, `informacoes`, `falar_atendente`, `outro_assunto`) — facilmente trocáveis.
- **Listas interativas nativas Meta** (`interactive/list`) com respeito aos limites oficiais (body 1024, button 20, 10 rows) e fallback numerado para Baileys.
- **Cadastro guiado** em 4 etapas: nome completo → CPF (com validação de dígitos verificadores) → data de nascimento (DD/MM/AAAA) → cidade/UF.
- **Sessão com expiração** (`SESSION_TIMEOUT_SECONDS`, padrão 1800s) e dados serializados em JSON.
- **Encaminhamento humano** com mensagem configurável (`HUMAN_ATTENDANT_NAME`) e estado `waiting_human`.
- **Tratamento Meta completo**: verificação `hub.challenge` via `PlainTextResponse`, `statuses` ignorados, `contacts/metadata` logados, `mark_as_read` best-effort.

---

## Estrutura do Projeto

```
.
├── app/
│   ├── config.py               # Settings — lê .env, expõe APP_NAME/BUSINESS_* e Meta/Baileys
│   ├── main.py                 # FastAPI — title/version via Settings, registra ambos routers
│   ├── data/
│   │   └── menus.py            # MENUS white-label (main + tópicos human)
│   ├── routes/
│   │   ├── webhook.py          # GET /webhook (verificação) e POST /webhook (Meta)
│   │   └── connector.py        # POST /webhook/connector (Baileys)
│   └── services/
│       ├── whatsapp.py         # WhatsAppService — Graph API + Connector
│       ├── menu.py             # MenuService — lista interativa / texto numerado
│       ├── conversation.py     # ConversationService — estado e roteamento
│       ├── registration.py     # RegistrationFlow — validações e coleta
│       └── session_store.py    # SessionStore — SQLite
├── .env.example                # Template white-label (copie para .env)
├── Dockerfile                  # python:3.13-slim + uvicorn
├── dockercompose.yml           # service api com env_file e volume data/
├── requirements.txt
├── runtime.txt                 # python-3.13.0
└── README.md
```

---

## Pré-requisitos

- Python 3.13+ (ou Docker)
- Conta Meta Developers com App configurado (para provider `meta`) **ou** Baileys Connector rodando
- `pip` ou `pipx` (PEP 668: use venv ou `--break-system-packages` em ambientes gerenciados)

---

## Instalação

### Local (venv recomendado)

```bash
cp .env.example .env
# edite .env com seus dados

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
# ou com env: PORT=8000 LOG_LEVEL=info uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verifique:

```bash
curl http://localhost:8000/health
# {"status":"ok","provider":"meta"}
```

### Docker

```bash
cp .env.example .env
docker compose up --build
# http://localhost:8000 (PORT do .env)
```

---

## Configuração

Todas as variáveis são lidas em `app/config.py` via `os.getenv`. Copie o template:

```bash
cp .env.example .env
```

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `APP_NAME` | não | `WhatsApp Chatbot` | Título da API (`FastAPI title`) |
| `APP_VERSION` | não | `1.1.0` | Versão exposta em `/` |
| `BUSINESS_NAME` | não | `Sua Empresa` | Nome exibido no menu `main.title` |
| `BUSINESS_DESCRIPTION` | não | `Atendimento automatizado via WhatsApp` | Uso interno/docs |
| `BUSINESS_FOOTER` | não | Texto LGPD | Rodapé do menu principal |
| `WELCOME_TITLE` | não | `Bem-vindo(a)!` | Título de boas-vindas |
| `WELCOME_BODY` | não | Texto genérico | Corpo de boas-vindas |
| `HUMAN_ATTENDANT_NAME` | não | `Equipe de Atendimento` | Nome usado em `menu.send_human` (alias `HUMAN_ATTENDANT`) |
| `WHATSAPP_PROVIDER` | não | `baileys` | `meta` ou `baileys` — define transporte de *envio* |
| `META_API_VERSION` | meta | `v25.0` | Versão da Graph API |
| `PHONE_NUMBER_ID` | meta | `` | ID do número (Meta > API Setup) |
| `WHATSAPP_TOKEN` | meta | `` | Token de longa duração (System User) |
| `VERIFY_TOKEN` | meta | `` | Token para verificação do webhook |
| `CONNECTOR_URL` | baileys | `http://localhost:3300` | Base do Baileys Connector |
| `CONNECTOR_SECRET` | baileys | `` | Bearer para `Authorization` |
| `SESSIONS_DB_PATH` | não | `data/sessions.db` | Caminho SQLite |
| `SESSION_TIMEOUT_SECONDS` | não | `1800` | TTL da sessão (30 min) |
| `PORT` | não | `8000` | Porta (Docker/host) |
| `LOG_LEVEL` | não | `info` | Nível de log |

> **Segurança:** `.env` está em `.gitignore`. Nunca comite tokens. O repositório versiona apenas `.env.example`.

---

## White Label

### 1. Marca via `.env`

Troque `BUSINESS_NAME`, `WELCOME_*`, `HUMAN_ATTENDANT_NAME` e `APP_NAME` — nenhuma alteração de código é necessária. Exemplo para cliente “Clínica Exemplo”:

```env
BUSINESS_NAME=Clínica Exemplo
WELCOME_TITLE=Olá, bem-vindo à Clínica Exemplo!
WELCOME_BODY=Escolha o assunto e nossa equipe dará continuidade.
HUMAN_ATTENDANT_NAME=Equipe Clínica Exemplo
```

### 2. Menus via `app/data/menus.py`

```python
MENUS = {
    "main": {
        "type": "list",
        "title": BUSINESS_NAME,
        "body": f"{BUSINESS_NAME}\n\n{WELCOME_TITLE}...",
        "button": "Ver opções",
        "rows": [
            {"id": "agendamento", "title": "Agendamento"},
            {"id": "resultados", "title": "Resultados"},
            # até 10 rows (limite Meta)
        ]
    },
    "agendamento": {"type": "human", "text": "Você selecionou Agendamento..."},
}
```

- Cada `row.id` deve existir como chave em `MENUS` com `type: human` ou `type: list`.
- Sincronize `id` com `TEXT_OPTIONS` em `app/services/conversation.py` (mapa `1`–`6` → `id`) e `TOPIC_LABELS` em `app/services/registration.py` (label exibido no resumo).

### 3. Sem hardcode

Use sempre `settings.BUSINESS_NAME` e `settings.HUMAN_ATTENDANT_NAME`. A busca `grep -R "Karol"` deve retornar vazio (exceto retrocompatibilidade de labels antigas, opcional).

---

## Integração Meta Cloud API

### Cadastro do Webhook

1. Em `developers.facebook.com` → seu App → WhatsApp → Configuration → Webhook → Edit → Callback URL: `https://seu-dominio/webhook`
2. Verify Token: igual ao `VERIFY_TOKEN` do `.env`
3. Subscribe a `messages`

A verificação é `GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` — o serviço responde `200 text/plain` com o `challenge` (`PlainTextResponse`), conforme exigência Meta.

### Envio

Quando `WHATSAPP_PROVIDER=meta`:

- **Texto:** `POST https://graph.facebook.com/{META_API_VERSION}/{PHONE_NUMBER_ID}/messages`
  ```json
  {"messaging_product":"whatsapp","recipient_type":"individual","to":"5511999999999","type":"text","text":{"preview_url":false,"body":"..."}}
  ```
  Header `Authorization: Bearer {WHATSAPP_TOKEN}`.

- **Lista interativa:** `type:interactive` → `interactive.type:list` com `header` (60), `body` (1024), `footer` (60), `action.button` (20) e `sections[0].rows` (10× title 24). Implementado em `WhatsAppService.send_interactive_list` e acionado por `MenuService` quando `provider == meta`; caso contrário, fallback numerado.

- **Leitura:** `mark_as_read` (`status:read`, `message_id`) — best-effort, sem falha do fluxo.

### Recebimento

`POST /webhook` recebe `whatsapp_business_account`:

```json
{
  "object":"whatsapp_business_account",
  "entry":[{"changes":[{"value":{
    "metadata":{"phone_number_id":"..."},
    "contacts":[{"profile":{"name":"..."},"wa_id":"5511..."}],
    "messages":[{"from":"5511...","id":"wamid...","type":"text","text":{"body":"oi"}}],
    "statuses":[]
  }}]}]
}
```

- `ConversationService.process` ignora `statuses`, loga `contacts/metadata`, marca `id` como lido e delega a `handle_message` (texto vs `interactive[list_reply|button_reply]`).
- Resposta ao webhook é imediata `200 {"status":"received"}` via `BackgroundTasks` — evita reenvio por timeout da Meta.

---

## Endpoints

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/` | — | `{application, business, provider, status}` |
| `GET` | `/health` | — | `{status, provider}` |
| `GET` | `/webhook` | `hub.verify_token` | Verificação Meta |
| `POST` | `/webhook` | — | Webhook Meta |
| `POST` | `/webhook/connector` | `Bearer CONNECTOR_SECRET` | Webhook Baileys (`{"from":"...","text":"..."}`) |
| `GET` | `/docs` | — | Swagger UI (FastAPI) |
| `GET` | `/openapi.json` | — | OpenAPI schema |

---

## Fluxo de Conversa

```
[Entrada] "oi" / "menu" / "" → clear + show main
[Sem sessão] → show main
[Estado em RegistrationFlow] → RegistrationFlow.handle (nome/CPF/nascimento/cidade)
[waiting_human] → "Você já está na fila..."
[Texto "1"–"6"] → TEXT_OPTIONS → _process_selection → menu.show + set state ou registration.start
[Interativo] → handle_interactive → _process_selection
```

Validações (`RegistrationFlow`):
- **Nome:** ≥2 partes, 5–120 chars, letras com `'`/`-`
- **CPF:** 11 dígitos + dígitos verificadores + rejeita repetidos
- **Nascimento:** `DD/MM/AAAA` estrito, ≤ hoje, idade ≤120
- **Cidade/UF:** `Cidade/UF` com UF 2 letras, cidade 2–100 chars

Ao concluir, envia resumo com `TOPIC_LABELS[topic]` e transita para `waiting_human`.

---

## Sessão e Persistência

`SessionStore` (`app/services/session_store.py`) usa SQLite:

```sql
CREATE TABLE sessions (phone TEXT PRIMARY KEY, state TEXT, topic TEXT, data TEXT, updated_at INTEGER)
```

- `get` verifica TTL (`SESSION_TIMEOUT_SECONDS`) e auto-limpa expirados.
- `set(phone, state, topic?, data?)` preserva campos não informados (merge com registro existente).
- Serialização `data` em JSON `ensure_ascii=False`.
- Acesso assíncrono via `asyncio.to_thread`.
- Arquivo padrão `data/sessions.db` (ignorado no git via `.gitignore` + `*.db`).

---

## Docker

```dockerfile
# Dockerfile — python:3.13-slim, httpx/fastapi, uvicorn 0.0.0.0:8000
```

```yaml
# dockercompose.yml
services:
  api:
    build: .
    ports: ["${PORT:-8000}:8000"]
    env_file: [.env]
    volumes: ["./data:/app/data"]
```

```bash
docker compose up --build
docker compose logs -f api
```

Para Baileys, adicione o serviço do conector e aponte `CONNECTOR_URL` para `http://connector:3300`.

---

## Testes

Teste manual rápido (requer `.env` com `CONNECTOR_URL` ou Meta configurado):

```bash
python app/tests/test_whatsapp.py
```

Testes de contrato Meta (mock sem rede):

```bash
python - << 'PY'
import asyncio
from unittest.mock import AsyncMock
from app.services.conversation import ConversationService

async def test():
    svc = ConversationService()
    svc.whatsapp.send_text = AsyncMock()
    svc.whatsapp.send_interactive_list = AsyncMock()
    svc.whatsapp.mark_as_read = AsyncMock()
    await svc.process({
      "object":"whatsapp_business_account",
      "entry":[{"changes":[{"value":{"messages":[{"from":"5511999999999","id":"wamid.1","type":"text","text":{"body":"oi"}}]}}]}]
    })
    assert svc.whatsapp.send_interactive_list.called or svc.whatsapp.send_text.called
    print("ok")

asyncio.run(test())
PY
```

Para testes HTTP do webhook, use `httpx`/`TestClient` contra `/webhook?hub.mode=subscribe...` (ver `app/routes/webhook.py`).

---

## Deploy

- **Variáveis obrigatórias em produção:** `PHONE_NUMBER_ID`, `WHATSAPP_TOKEN`, `VERIFY_TOKEN` (meta) ou `CONNECTOR_SECRET` (baileys), `SESSIONS_DB_PATH` em volume persistente.
- **Webhook público:** exponha `/webhook` via HTTPS (ex.: Nginx, Cloud Run, Fly.io). Cadastre a URL no painel Meta.
- **Logs:** `LOG_LEVEL=info` (padrão) — `WhatsAppService` loga `status/body` em erro e `raise_for_status`.
- **Escala:** SQLite é suficiente para demo/single-instance; para multi-instância, migre `SessionStore` para Redis/Postgres.

---

## Troubleshooting

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `Meta não configurado: PHONE_NUMBER_ID ou WHATSAPP_TOKEN vazio` | `.env` sem credenciais | Preencha `PHONE_NUMBER_ID` e `WHATSAPP_TOKEN` |
| Webhook retorna 403 na verificação | `VERIFY_TOKEN` divergente | Garanta mesmo valor no painel Meta e `.env` |
| Lista não aparece, cai em texto | Limite Meta excedido ou token inválido | Verifique logs `Meta lista erro ...` e respeite 10 rows / title 24 |
| `401 Unauthorized` em `/webhook/connector` | `Authorization` incorreto | Envie `Bearer {CONNECTOR_SECRET}` |
| Mensagens reenviadas pela Meta | Webhook lento | `POST /webhook` responde 200 imediato via `BackgroundTasks` — mantenha `process` leve |

---

## Contribuição

1. Crie um branch (`feat/minha-feature`)
2. Mantenha white-label: não hardcodeie marcas; use `settings` e `.env.example`
3. Respeite limites Meta em `whatsapp.py`/`menu.py`
4. Rode verificação manual (`TestClient` + `httpx` mock)
5. Abra PR com descrição e screenshots do fluxo

---

## Licença

Uso interno / white-label. Adapte a licença conforme o cliente final. O template é distribuído sem garantias — ajuste `BUSINESS_FOOTER` para conformidade com LGPD do seu caso.

---

> Dúvidas sobre a integração Meta? Consulte a [documentação oficial](https://developers.facebook.com/docs/whatsapp/cloud-api) e os comentários em `app/services/whatsapp.py` e `app/data/menus.py`.
