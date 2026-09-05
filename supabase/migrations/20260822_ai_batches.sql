-- Soporte para Batch API de Anthropic en ai_analyst.py (submit/collect
-- separados: la Batch API es async, minutos a 24h de turnaround, no se
-- puede esperar sincrono dentro de un solo step de GitHub Actions).
CREATE TABLE IF NOT EXISTS public.ai_batches (
    id BIGSERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,       -- id que devuelve Anthropic
    n_requests INTEGER,
    noticia_ids JSONB,                    -- [id1, id2, ...] para mapear custom_id -> noticia
    status TEXT DEFAULT 'submitted',      -- submitted | ended | collected | error
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    collected_at TIMESTAMPTZ
);

ALTER TABLE public.ai_batches ENABLE ROW LEVEL SECURITY;
