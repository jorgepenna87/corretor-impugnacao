grant select, insert
on table public.ai_request_log
to service_role;

grant usage, select
on sequence public.ai_request_log_id_seq
to service_role;