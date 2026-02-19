# Agent State and Supabase

This document describes how the LangGraph agent uses **state** and how **Supabase** is used for persistence (conversations, memory, user context, and knowledge base).

---

## 1. Agent state (LangGraph)

### State schema

The agent uses **`MessagesState`** from LangGraph: a state type whose only key is `messages`, a list of LangChain message objects (`BaseMessage`).

- **Input:** Each invocation receives `{"messages": [ ... ]}` (e.g. system prompt, prior conversation, latest user message).
- **Nodes read:** `state["messages"]` to get the full conversation so far.
- **Nodes return:** **Partial updates** (deltas), e.g. `{"messages": [new_ai_message]}`. They do **not** return the full state.

### Reducer

`MessagesState` uses a **reducer** for the `messages` key: updates from nodes are **merged** (typically appended or merged by message ID), not replaced. So:

1. You pass in `messages = [SystemMessage(...), HumanMessage(...)]`.
2. **Agent node** returns `{"messages": [AIMessage(...)]}` → state becomes `[sys, human, ai]`.
3. **Tool node** (when the AI requested tools) returns `{"messages": [ToolMessage(...), ...]}` → state becomes `[..., ai, tool_msg]`.
4. **Agent node** runs again and may return another `{"messages": [AIMessage(...)]}` → state becomes `[..., tool_msg, ai_final]`.
5. This repeats until the agent responds without tool calls, then the graph goes to `END`.

### What `invoke()` returns

**`compiled.invoke({"messages": messages})`** returns the **full state** after the run, not just the new messages. So:

- `result = invoke_agent(messages)`
- `result["messages"]` = **complete** list of messages (input + all messages added by agent and tools during this run).

The API layer uses `result["messages"]` as the full conversation for saving and for taking the final reply (last message). It does **not** merge `input_messages + result["messages"]`, which would duplicate the input.

### Flow summary

| Step | Who | Reads state | Returns (delta) |
|------|-----|-------------|------------------|
| 1 | `agent` node | `state["messages"]` | `{"messages": [AIMessage]}` |
| 2 | `should_continue` | `state["messages"][-1]` | `"tools"` or `END` |
| 3 | `tools` node (ToolNode) | state (for tool dispatch) | `{"messages": [ToolMessage, ...]}` |
| 4 | back to `agent` | updated `state["messages"]` | … repeat until END |

So the agent **does** use state correctly: single key `messages`, reducer merges updates, and the API consumes the **full** `result["messages"]` as the conversation after the run.

---

## 2. Supabase: overview

When `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set, the app uses Supabase for:

1. **Conversation persistence** – load/save chat history per `session_id`
2. **Long-term memory** – store and recall user facts (vector search)
3. **User context** – plan, usage, preferences per `user_id`
4. **Knowledge base** – RAG over internal docs/FAQs (vector search)

All of this is optional; without Supabase, the agent still runs but with no persistence or memory tools.

---

## 3. Supabase tables and usage

### 3.1 `agent_conversations`

**Purpose:** One row per chat session; stores the message history for that session.

| Column (typical) | Type | Description |
|------------------|------|-------------|
| `session_id` | text (PK) | Unique session id (e.g. UUID from API). |
| `messages` | jsonb | List of message dicts (LangChain `messages_to_dict` format). |
| `updated_at` | timestamptz | Last update time. |
| `user_id` | text (optional) | Optional user id for multi-tenant. |

**Used by:**

- **`get_conversation(session_id)`** – loads messages for a session, converts them back to `BaseMessage` with `messages_from_dict`, and returns them so the API can prepend them to the next request.
- **`save_conversation(session_id, messages, user_id)`** – upserts one row (on conflict `session_id`). The API saves an “answers only” version (system, user, and AI reply content; tool calls and tool results are stripped to keep storage smaller).

**When it runs:**  
On each `POST /api/chat`, if `session_id` is provided and Supabase is enabled, the route loads history with `get_conversation(req.session_id)`, then after the agent run saves the full conversation (answers only) with `save_conversation(...)`.

---

### 3.2 `agent_memories`

**Purpose:** Long-term semantic memory: atomic facts (preferences, decisions, constraints) with vector embeddings for similarity search.

| Column (typical) | Type | Description |
|------------------|------|-------------|
| `id` | uuid | Primary key. |
| `user_id` | text (optional) | Scope memories to a user; `NULL` = global. |
| `content` | text | The fact to remember. |
| `embedding` | vector | Embedding of `content` (dimension from `EMBEDDING_DIM`). |

**Used by:**

- **`store_memory(content, user_id)`** – tool that embeds `content` and inserts one row into `agent_memories`. Used when the user says “remember that …”.
- **`recall_memory(query, user_id)`** – tool that embeds `query`, then calls the **`match_memories`** RPC to get the top‑k similar memories (optionally filtered by `user_id`), and returns their `content`.
- **Post-response memory extraction** – after each chat response, `extract_memory_facts(user_message, assistant_reply)` distills 0–5 facts; `persist_memory_facts(user_id, facts)` embeds each and inserts into `agent_memories`. So memories can be created without the user explicitly saying “remember”.

**RPC:**  
- **`match_memories(query_embedding, match_count, filter_user_id)`** – returns rows from `agent_memories` ordered by embedding similarity to `query_embedding`, optionally filtered by `filter_user_id`. Implemented in SQL (e.g. `pgvector` `<=>` or similar). Required for `recall_memory` to work.

---

### 3.3 `user_context`

**Purpose:** Key-value–style user metadata (plan, usage, preferences) for personalization.

| Column (typical) | Type | Description |
|------------------|------|-------------|
| `user_id` | text (PK) | User identifier. |
| `plan` | text | e.g. free / pro / enterprise. |
| `usage` | text / jsonb | Usage or stats. |
| `preferences` | text / jsonb | User preferences. |

**Used by:**

- **`get_user_context(user_id)`** – tool that selects `plan`, `usage`, `preferences` for the given `user_id` and returns a short text summary. The model uses this when it needs the user’s tier, limits, or settings.

**Note:** The API accepts an optional `user_id` on the chat request; it is not automatically passed into graph state. The model can only use it if the client sends it and the model passes it to tools (e.g. `recall_memory(..., user_id)` or `get_user_context(user_id)`).

---

### 3.4 `knowledge_chunks`

**Purpose:** RAG over internal docs, FAQs, and policies (vector search).

| Column (typical) | Type | Description |
|------------------|------|-------------|
| `id` | uuid | Primary key. |
| `content` | text | Chunk text. |
| `source` | text | Document/section name or URL. |
| `embedding` | vector | Embedding of `content`. |

**Used by:**

- **`search_knowledge_base(query)`** – tool that embeds `query`, calls the **`match_knowledge`** RPC, and returns matching chunks (e.g. `source` + `content`). Used when the user asks about company info or documented knowledge.
- **Ingest script** – e.g. `scripts/ingest_knowledge.py` (or similar) can insert rows from JSON/files; embeddings are usually computed before insert.

**RPC:**  
- **`match_knowledge(query_embedding, match_count)`** – returns rows from `knowledge_chunks` ordered by embedding similarity. Required for `search_knowledge_base` to work.

---

## 4. Summary diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  POST /api/chat (message, session_id?, user_id?)                         │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  If Supabase + session_id: get_conversation(session_id) → messages       │
│  Prepend system prompt if new conversation; append HumanMessage          │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  invoke_agent({"messages": messages})  →  LangGraph run                  │
│  State: MessagesState (reducer merges messages)                          │
│  Nodes: agent → [tools] → agent → … → END                                │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  result["messages"] = full state (all messages after run)                 │
│  reply = last message content                                            │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  If Supabase: save_conversation(session_id, answers_only(full_messages))  │
│  If Supabase: extract_memory_facts + persist_memory_facts(user_id, facts) │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  return ChatResponse(reply=..., session_id=...)                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Supabase usage during a run:**

- **Before invoke:** `agent_conversations` (read by session).
- **During invoke:** Tools may read/write `agent_memories` (recall_memory, store_memory), read `user_context` (get_user_context), read `knowledge_chunks` via `match_knowledge` (search_knowledge_base).
- **After invoke:** `agent_conversations` (write), `agent_memories` (write from memory extraction).

---

## 5. Env and migrations

- **Env:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_KEY`). Use the **service role** key, not the anon key.
- **Migrations:** Run the project’s Supabase migrations in order (e.g. `001_agent_conversations.sql`, `002_agent_memories_and_user_context.sql`, `003_knowledge_chunks.sql` if present) in the Supabase SQL Editor so tables and RPCs (`match_memories`, `match_knowledge`) exist. See the main **README** for exact file names and instructions.

This keeps the agent state correct (single source of truth in `result["messages"]`) and makes Supabase usage for memory and other tables explicit and documented.
