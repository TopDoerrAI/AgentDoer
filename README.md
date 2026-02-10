# NVIDIA Agent (Production)

LangGraph + LangChain agent with browser tools, web search, and optional Supabase persistence, exposed via FastAPI.

## Structure

```
NVIDIA-LLM/
├── app/
│   ├── main.py           # FastAPI app
│   ├── api/routes.py     # POST /api/chat, GET /api/health
│   ├── core/
│   │   ├── config.py     # Settings from env
│   │   ├── agent.py      # LangGraph agent (build + invoke)
│   │   └── supabase_client.py  # Optional conversation persistence
│   └── models/schemas.py # ChatRequest, ChatResponse
├── tools/
│   ├── browser/         # get_page, open_url, click, fill, press_enter, page_content
│   └── web_search.py
├── supabase/migrations/  # SQL for agent_conversations table
├── main.py              # CLI: run one prompt (legacy)
├── requirements.txt
└── .env / .env.example
```

## Setup

1. **Env**
   ```bash
   cp .env.example .env
   # Edit .env: set NVIDIA_API_KEY, optionally SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
   ```

2. **Supabase (optional)**  
   In the [Supabase SQL Editor](https://supabase.com/dashboard/project/_/sql), run the migrations in order so the app can persist conversations and long-term memory:
   - **001_agent_conversations.sql** – chat history per session  
   - **002_agent_memories_and_user_context.sql** – long-term memory (recall_memory / store_memory) and the `match_memories` RPC. **Required** if you use memory tools or post-response memory extraction; otherwise you’ll see: `Could not find the table 'public.agent_memories'`.  
   - **003_knowledge_chunks.sql** – only if you use the knowledge base (search_knowledge_base).  
   Run each file’s SQL in the same project as your `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`.

3. **Install**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## Run

**API (production)**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Docs: http://localhost:8000/docs  
- Chat: `POST /api/chat` with body `{"message": "Hello", "session_id": "optional-uuid"}`

**CLI (one-off prompt)**
```bash
python main.py
```
Uses the same agent; edit the `prompt` variable in `main.py` or pass via env.

## API

- **POST /api/chat**  
  Body: `{ "message": "user text", "session_id": "optional", "user_id": "optional" }`  
  Returns: `{ "reply": "agent reply", "session_id": "..." }`  
  Use the same `session_id` for multi-turn conversations. If Supabase is configured, history is stored and loaded by session.

- **GET /api/health**  
  Returns `{ "status": "ok" }`.

## Env

| Variable | Description |
|----------|-------------|
| `NVIDIA_API_KEY` | Required for the LLM |
| `NVIDIA_MODEL` | Optional model override |
| `USE_TOOLS` | `1` to enable browser + search tools |
| `BROWSER_HEADLESS` | `0` to show the browser window |
| `SUPABASE_URL` | Optional; enables conversation persistence |
| `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_KEY` | Optional; required if using Supabase |

## Troubleshooting

- **`Could not find the table 'public.agent_memories'`**  
  Run the second migration: in Supabase → SQL Editor, execute the contents of `supabase/migrations/002_agent_memories_and_user_context.sql`. That creates the `agent_memories` table and the `match_memories` function used by recall_memory, store_memory, and post-response memory extraction.
