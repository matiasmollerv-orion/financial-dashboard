-- ============================================================
-- NOTIFICACIONES iPhone → Supabase
-- Ejecutar UNA VEZ en Supabase SQL Editor
-- ============================================================

-- Staging: cada notificación cruda que llega del iPhone
CREATE TABLE IF NOT EXISTS notification_inbox (
    id              BIGSERIAL PRIMARY KEY,
    fecha_recibido  TIMESTAMPTZ DEFAULT NOW(),
    raw_text        TEXT NOT NULL,
    source          TEXT,                -- 'santander_tc' / 'santander_cc' / etc.

    -- Parsing
    parsed_monto       NUMERIC,
    parsed_descripcion TEXT,
    parsed_moneda      TEXT,
    parse_error        TEXT,

    -- Reconciliación
    procesado       BOOLEAN DEFAULT FALSE,
    gasto_id        BIGINT REFERENCES santander_gastos(id) ON DELETE SET NULL,
    reconciliado    BOOLEAN DEFAULT FALSE,         -- true si ya matcheó con PDF mensual

    -- Metadata
    user_agent      TEXT,
    ip              TEXT
);

CREATE INDEX IF NOT EXISTS idx_notif_procesado ON notification_inbox(procesado);
CREATE INDEX IF NOT EXISTS idx_notif_fecha ON notification_inbox(fecha_recibido DESC);
CREATE INDEX IF NOT EXISTS idx_notif_reconciliado ON notification_inbox(reconciliado);

-- Asegurar que santander_gastos tenga columna 'fuente' para distinguir origen
-- (probablemente ya existe, este ALTER es idempotente)
ALTER TABLE santander_gastos
    ADD COLUMN IF NOT EXISTS fuente TEXT;
