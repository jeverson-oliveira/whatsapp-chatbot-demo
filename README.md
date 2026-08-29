# WhatsApp Chatbot — White Label

Chatbot genérico para WhatsApp com suporte a **Meta Cloud API** e **Baileys Connector**. Projeto white-label: toda identidade (nome da empresa, mensagens, atendente, menus) é configurável via `.env` e `app/data/menus.py`.

## Recursos

- Menu principal genérico (6 opções neutras) + cadastro guiado (nome, CPF, nascimento, cidade/UF)
- Persistência de sessão em SQLite (`SessionStore`)
- Suporte a mensagens de texto e interativas (Meta) + conector simplificado (Baileys)
- Encaminhamento para atendimento humano
- Configuração 100% por variáveis de ambiente

## Quick Start

```bash
cp .env.example .env
# edite .env com seus dados
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Endpoints (Meta compatível):
- `GET /` — info da aplicação
- `GET /health` — health check
- `GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` — verificação Meta (retorna `PlainTextResponse` com challenge)
- `POST /webhook` — webhook Meta (`whatsapp_business_account` com `entry.changes.value.messages[].type=text|interactive`)
- `POST /webhook/connector` — webhook Baileys (header `Authorization: Bearer <CONNECTOR_SECRET>`)

### Meta Cloud API — Compatibilidade

- `WhatsAppService` envia via Graph API `https://graph.facebook.com/{META_API_VERSION}/{PHONE_NUMBER_ID}/messages` com `Authorization: Bearer {WHATSAPP_TOKEN}` quando `WHATSAPP_PROVIDER=meta`
- `MenuService` detecta provider: para Meta envia **listas interativas nativas** (`type: interactive/list`, limites Meta: body 1024, button 20, rows 10); para Baileys faz fallback para texto numerado
- `ConversationService.process` trata `statuses` (ignora), `contacts/metadata` (log), `messages[].id` (marca como lida via `mark_as_read`), e `interactive[list_reply|button_reply]`
- Ambos os routers são registrados sempre (`app/main.py`), permitindo switch de provider sem restart

## White Label — Como customizar

1. **Variáveis no `.env`:**
   - `APP_NAME`, `BUSINESS_NAME`, `BUSINESS_DESCRIPTION`, `BUSINESS_FOOTER`
   - `WELCOME_TITLE`, `WELCOME_BODY`
   - `HUMAN_ATTENDANT_NAME` / `HUMAN_ATTENDANT`
   - `WHATSAPP_PROVIDER` (`meta` ou `baileys`)

2. **Menus em `app/data/menus.py`:**
   - Edite `MENUS["main"]["rows"]` para trocar títulos/IDs
   - Adicione/ajuste blocos `type: human` ou `type: list`
   - IDs devem coincidir com `TEXT_OPTIONS` em `app/services/conversation.py` e `TOPIC_LABELS` em `app/services/registration.py`

3. **Sem hardcode de marca:** use `settings.BUSINESS_NAME` e `settings.HUMAN_ATTENDANT_NAME` no código.

## Estrutura

```
app/
  config.py              # Settings (lê .env)
  main.py                # FastAPI (app = APP_NAME)
  data/menus.py          # MENUS genéricos
  services/
    conversation.py      # Fluxo principal (TEXT_OPTIONS genérico)
    registration.py      # Cadastro + TOPIC_LABELS genérico
    menu.py              # Exibe menus (usa HUMAN_ATTENDANT_NAME)
    whatsapp.py          # Envio via Graph API / Connector
    session_store.py     # SQLite
  routes/
    webhook.py           # Meta
    connector.py         # Baileys
```

## Variáveis de ambiente

Veja `.env.example` para lista completa. Principais:

| Variável | Descrição |
|---|---|
| `WHATSAPP_PROVIDER` | `meta` ou `baileys` |
| `CONNECTOR_URL/SECRET` | Baileys connector |
| `META_API_VERSION`, `PHONE_NUMBER_ID`, `WHATSAPP_TOKEN`, `VERIFY_TOKEN` | Meta |
| `SESSIONS_DB_PATH`, `SESSION_TIMEOUT_SECONDS` | Sessão |
| `APP_NAME`, `BUSINESS_NAME`, `HUMAN_ATTENDANT_NAME` | White label |

## Docker (opcional)

```bash
docker compose up --build
```

## Licença

Uso interno / white-label. Ajuste conforme o cliente final.
