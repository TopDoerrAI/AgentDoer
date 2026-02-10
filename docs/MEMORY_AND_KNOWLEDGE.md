# Memory & knowledge (anchor doc)

## Big rule

**Do NOT vectorize conversations verbatim. Vectorize distilled meaning.**

Memory quality > quantity. One row = one idea.

---

## 1. `agent_memories` — long-term semantic memory

**Purpose:** Durable, cross-session memory. Atomic facts, not chats.

### Store (YES)

- User preferences — e.g. "User prefers concise answers"
- Decisions — e.g. "Chose Supabase Auth over backend auth"
- Constraints — e.g. "Do not expose chain-of-thought to users"
- Architecture / design tradeoffs, user role, goals, product direction

**One row = ONE idea.**  
`content` = single sentence or short paragraph.

### Do NOT store

- "Hi", "Thanks", turn-by-turn chat, temporary questions, tool logs

### How it’s populated

- **After each agent turn:** run extraction on (user message + assistant reply) → 0..N facts → embed + insert. If nothing memory-worthy, insert nothing.
- **Tool `store_memory`:** model can store one atomic fact per call; do not store chat verbatim.

### Retrieval

- Use when: "remember", "last time", "what did we decide", or personalization is needed.
- `match_memories(query_embedding, 5, user_id)` → inject as "Relevant past context: ..."

---

## 2. `knowledge_chunks` — RAG / ground truth

**Not conversation memory.** Static, authoritative, reusable.

### Store (YES)

- Product/docs, API docs, pricing rules, policies, runbooks, FAQs, compliance text
- Chunk size: ~300–800 tokens, one concept per chunk
- `content` = chunk text, `source` = doc/section id

### Do NOT store

- User opinions, preferences, or chat transcripts (those go in `agent_memories` or not at all)

### How it’s populated

- **At ingest time:** document → chunk → embed → insert into `knowledge_chunks`. Not at query time.
- Use the JSON array format (see `examples/knowledge_chunks_example.json`) and an ingest script that embeds and inserts.

### Retrieval

- Use when: factual / how-to questions, architecture, docs, policies.
- `match_knowledge(query_embedding, 5)` → inject as "Use the following knowledge to answer: ..."

---

## 3. `user_context` — structured state (no embeddings)

- **Store:** plan, usage counters, explicit settings, feature flags.
- **Retrieve:** `get_user_context(user_id)`; do not embed.

---

## 4. Timing

| What              | When            |
|-------------------|-----------------|
| Memory extraction | After agent response |
| Memory insert     | After extraction (if facts ≠ NONE) |
| Knowledge embed   | At ingest time (when adding docs)  |

---

## 5. Embedding size

- Table columns: `vector(1024)`.
- Use an embedding model that outputs **1024** dimensions (e.g. NVIDIA `nvidia/nv-embedqa-e5-v5`). Mismatch = silent failure or bad search.

---

## 6. Example data & ingest

- **knowledge_chunks:** `examples/knowledge_chunks_example.json` — array of `{ "source", "content" }`. Ingest (embeds and inserts):  
  `python scripts/ingest_knowledge.py examples/knowledge_chunks_example.json`
- **agent_memories:** `examples/agent_memories_example.json` — example content strings (one fact per line). Populated by post-response extraction and by the `store_memory` tool; do not ingest chat verbatim.
- **user_context:** `examples/user_context_example.json` — array of `{ "user_id", "plan", "usage", "preferences" }`. Insert via Supabase or your app; no embedding.
