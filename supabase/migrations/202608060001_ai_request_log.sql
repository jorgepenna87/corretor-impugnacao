create table if not exists public.ai_request_log (
  id bigint generated always as identity primary key,
  fingerprint text not null,
  exercise text not null check (exercise in ('marco16', 'abril13', 'junho22', 'setembro15')),
  created_at timestamptz not null default now()
);

create index if not exists ai_request_log_fingerprint_created_at_idx
  on public.ai_request_log (fingerprint, created_at desc);

alter table public.ai_request_log enable row level security;

-- Nenhum acesso direto pelo navegador. A Edge Function usa service_role.
revoke all on table public.ai_request_log from anon, authenticated;

comment on table public.ai_request_log is
  'Log mínimo para rate limit da análise por IA. Não armazena textos, arquivos, respostas nem IP em formato legível.';
