-- Long-term semantic memory (pgvector) and user context for agent tools.
-- Run: create extension if not exists vector; then this migration.

create extension if not exists vector;

-- Memories: store/recall by embedding similarity (optional user_id for multi-tenant)
create table if not exists agent_memories (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  content text not null,
  embedding vector(1024),
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_memories_user_id on agent_memories (user_id);
-- HNSW works on empty tables; use cosine for similarity search
create index if not exists idx_agent_memories_embedding on agent_memories
  using hnsw (embedding vector_cosine_ops);

alter table agent_memories enable row level security;
create policy "Allow service role full access" on agent_memories for all using (true) with check (true);

-- RPC for similarity search (embedding passed as text so PostgREST can send it)
create or replace function match_memories(
  query_embedding text,
  match_count int default 5,
  filter_user_id text default null
)
returns setof agent_memories
language sql stable
as $$
  select * from agent_memories
  where embedding is not null
    and (filter_user_id is null or user_id = filter_user_id)
  order by embedding <=> query_embedding::vector(1024)
  limit match_count;
$$;

-- User context: plan, usage, preferences (for get_user_context tool)
create table if not exists user_context (
  user_id text primary key,
  plan text,
  usage jsonb default '{}',
  preferences jsonb default '{}',
  updated_at timestamptz not null default now()
);

alter table user_context enable row level security;
create policy "Allow service role full access" on user_context for all using (true) with check (true);
