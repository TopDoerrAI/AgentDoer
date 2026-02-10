-- Run this in Supabase SQL Editor to create the conversations table.

create table if not exists agent_conversations (
  session_id text primary key,
  user_id text,
  messages jsonb not null default '[]',
  updated_at timestamptz not null default now()
);

-- Optional: RLS (use anon key for client access; service role bypasses RLS)
alter table agent_conversations enable row level security;

create policy "Allow service role full access"
  on agent_conversations
  for all
  using (true)
  with check (true);

-- Optional: index for listing by user
create index if not exists idx_agent_conversations_user_id
  on agent_conversations (user_id);
create index if not exists idx_agent_conversations_updated_at
  on agent_conversations (updated_at desc);
