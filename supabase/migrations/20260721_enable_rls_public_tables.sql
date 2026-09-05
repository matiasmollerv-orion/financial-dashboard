-- Activa RLS en las 5 tablas que Supabase Security Advisor marcó como
-- "RLS Disabled in Public". Sin políticas: todo el proyecto usa la key
-- service_role (bypasea RLS por diseño), así que esto no cambia el
-- comportamiento de GitHub Actions ni de Streamlit — solo bloquea por
-- default cualquier acceso futuro con la key anon.

ALTER TABLE public.racional_nacional_detalle ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crypto_saldo_base          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_inbox         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_stats             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scouting_deep_ondemand     ENABLE ROW LEVEL SECURITY;
