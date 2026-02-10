-- Knowledge base for search_knowledge_base tool (RAG from Supabase).
-- Populate via Supabase Studio, API, or an ingest script; then the agent searches by embedding.

create table if not exists knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  source text,
  content text not null,
  embedding vector(1024),
  created_at timestamptz not null default now()
);

create index if not exists idx_knowledge_chunks_embedding on knowledge_chunks
  using hnsw (embedding vector_cosine_ops);

alter table knowledge_chunks enable row level security;
create policy "Allow service role full access" on knowledge_chunks for all using (true) with check (true);

create or replace function match_knowledge(
  query_embedding text,
  match_count int default 5
)
returns setof knowledge_chunks
language sql stable
as $$
  select * from knowledge_chunks
  where embedding is not null
  order by embedding <=> query_embedding::vector(1024)
  limit match_count;
$$;
