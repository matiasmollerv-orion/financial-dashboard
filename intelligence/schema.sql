-- ============================================================
-- SCHEMA: INTELIGENCIA DE MERCADO
-- Ejecutar UNA VEZ en Supabase SQL Editor antes de usar el módulo
-- ============================================================

-- Tabla 1: Noticias crudas filtradas por relevancia básica
CREATE TABLE IF NOT EXISTS market_news (
    id BIGSERIAL PRIMARY KEY,
    fecha_noticia TIMESTAMPTZ,
    fecha_proceso TIMESTAMPTZ DEFAULT NOW(),
    titulo TEXT NOT NULL,
    resumen TEXT,
    url TEXT UNIQUE,
    fuente TEXT,

    tickers_mencionados TEXT[],     -- detectados por keyword match (preliminar)
    sectores_mencionados TEXT[],

    procesado_ai BOOLEAN DEFAULT FALSE,
    relevancia_preliminar INT       -- 0-100, basado en keyword match
);
CREATE INDEX IF NOT EXISTS idx_news_fecha ON market_news(fecha_noticia DESC);
CREATE INDEX IF NOT EXISTS idx_news_procesado ON market_news(procesado_ai);

-- Tabla 2: Análisis AI por noticia
CREATE TABLE IF NOT EXISTS market_intelligence (
    id BIGSERIAL PRIMARY KEY,
    noticia_id BIGINT REFERENCES market_news(id) ON DELETE CASCADE,
    fecha_analisis TIMESTAMPTZ DEFAULT NOW(),

    relevancia_pct INT,             -- 0-100
    tipo TEXT,                      -- 'riesgo' | 'oportunidad' | 'neutro'
    horizonte TEXT,                 -- 'intraday' | 'semanas' | 'meses' | 'estructural'
    confianza_senal TEXT,           -- 'ruido' | 'baja' | 'media' | 'alta'

    tickers_afectados TEXT[],
    sectores_afectados TEXT[],
    impacto_estimado_pct NUMERIC(5,2),    -- estimado: -10 a +10 %
    pct_cartera_expuesta NUMERIC(5,2),    -- 0-100

    resumen_esp TEXT,
    razonamiento TEXT,
    contraargumento TEXT,
    accion_sugerida TEXT,

    modelo_usado TEXT
);
CREATE INDEX IF NOT EXISTS idx_intel_fecha ON market_intelligence(fecha_analisis DESC);
CREATE INDEX IF NOT EXISTS idx_intel_tipo ON market_intelligence(tipo);

-- Tabla 3: Alertas independientes de cartera (no requieren noticias)
CREATE TABLE IF NOT EXISTS portfolio_alerts (
    id BIGSERIAL PRIMARY KEY,
    fecha_alerta TIMESTAMPTZ DEFAULT NOW(),

    categoria TEXT,                 -- 'concentracion'|'valuacion'|'drawdown'|'volatilidad'|
                                    -- 'stale'|'cambiaria'|'liquidez'|'crypto'|'salud_global'
    severidad TEXT,                 -- 'critica'|'alta'|'media'|'baja'|'info'
    activo TEXT,                    -- ticker afectado o 'PORTFOLIO' para alertas globales
    titulo TEXT,
    mensaje TEXT,

    metricas JSONB,                 -- raw metrics para auditar y debug
    sugerencia TEXT,

    activo_alerta BOOLEAN DEFAULT TRUE,    -- false si ya fue resuelta
    visto_user BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alerts_activas ON portfolio_alerts(activo_alerta);
CREATE INDEX IF NOT EXISTS idx_alerts_severidad ON portfolio_alerts(severidad);
-- Idempotencia: misma alerta no se duplica el mismo día
CREATE UNIQUE INDEX IF NOT EXISTS uniq_alert_per_day
    ON portfolio_alerts (categoria, activo, ((fecha_alerta AT TIME ZONE 'UTC')::date));
