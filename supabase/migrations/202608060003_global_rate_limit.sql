-- Índice para acelerar a contagem global de chamadas na última hora.
create index if not exists ai_request_log_created_at_idx
  on public.ai_request_log (created_at desc);