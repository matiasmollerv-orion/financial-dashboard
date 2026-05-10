-- ============================================================
-- FINANCIAL DASHBOARD - Schema Supabase
-- Ejecutar en: Supabase → SQL Editor
-- ============================================================

-- ── INVERSIONES RACIONAL (internacionales + nacionales) ────
CREATE TABLE IF NOT EXISTS racional_transacciones (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    tipo            TEXT DEFAULT 'compra',
    mercado         TEXT NOT NULL,           -- 'internacional' | 'nacional'
    empresa         TEXT,
    ticker          TEXT,
    acciones        NUMERIC,
    precio_usd      NUMERIC,
    monto_usd       NUMERIC,
    monto_clp       NUMERIC,
    moneda          TEXT,
    fuente          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Detalle por acción del portafolio nacional
CREATE TABLE IF NOT EXISTS racional_nacional_detalle (
    id                      BIGSERIAL PRIMARY KEY,
    transaccion_id          BIGINT REFERENCES racional_transacciones(id),
    fecha                   DATE NOT NULL,
    ticker                  TEXT NOT NULL,
    monto_clp               NUMERIC,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ── CRYPTO BUDA ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS buda_crypto (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    tipo            TEXT DEFAULT 'compra_programada',
    activo          TEXT NOT NULL,           -- 'BTC' | 'ETH'
    cantidad        NUMERIC NOT NULL,
    moneda          TEXT,
    fuente          TEXT DEFAULT 'buda_email',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Saldo base crypto (ingresado manualmente)
CREATE TABLE IF NOT EXISTS crypto_saldo_base (
    id              BIGSERIAL PRIMARY KEY,
    activo          TEXT NOT NULL,
    cantidad        NUMERIC NOT NULL,
    fecha_corte     DATE NOT NULL,           -- fecha hasta la que es válido este saldo
    nota            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── VECTOR CAPITAL (validación mensual) ───────────────────
CREATE TABLE IF NOT EXISTS vector_capital_comprobantes (
    id              BIGSERIAL PRIMARY KEY,
    archivo         TEXT UNIQUE,
    fecha           DATE,
    tipo            TEXT,                    -- 'compra' | 'comision'
    instrumento     TEXT,
    moneda          TEXT,
    precio          NUMERIC,
    cantidad        NUMERIC,
    monto           NUMERIC,
    es_comision     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── GASTOS SANTANDER TARJETA ──────────────────────────────
CREATE TABLE IF NOT EXISTS santander_gastos (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    descripcion     TEXT,
    monto           NUMERIC NOT NULL,
    moneda          TEXT DEFAULT 'CLP',      -- 'CLP' | 'USD'
    categoria       TEXT DEFAULT 'Otros',
    fuente          TEXT DEFAULT 'santander_tarjeta',
    archivo         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── MOVIMIENTOS CUENTA CORRIENTE ──────────────────────────
CREATE TABLE IF NOT EXISTS santander_cuenta (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    descripcion     TEXT,
    monto           NUMERIC NOT NULL,
    saldo           NUMERIC,
    tipo            TEXT,                    -- 'abono' | 'cargo'
    moneda          TEXT DEFAULT 'CLP',
    archivo         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── INGRESOS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingresos (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    concepto        TEXT NOT NULL,           -- 'sueldo', 'bono', etc.
    monto           NUMERIC NOT NULL,
    moneda          TEXT DEFAULT 'CLP',
    fuente          TEXT DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── CARTERA ACTUAL (ingreso manual) ───────────────────────
CREATE TABLE IF NOT EXISTS cartera_actual (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    empresa         TEXT,
    mercado         TEXT,                    -- 'internacional' | 'nacional' | 'crypto'
    cantidad        NUMERIC,
    precio_compra   NUMERIC,
    precio_actual   NUMERIC,
    moneda          TEXT,
    fecha_actualizacion DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── ÍNDICES para consultas rápidas ───────────────────────
CREATE INDEX IF NOT EXISTS idx_racional_fecha    ON racional_transacciones(fecha);
CREATE INDEX IF NOT EXISTS idx_racional_ticker   ON racional_transacciones(ticker);
CREATE INDEX IF NOT EXISTS idx_racional_mercado  ON racional_transacciones(mercado);
CREATE INDEX IF NOT EXISTS idx_buda_fecha        ON buda_crypto(fecha);
CREATE INDEX IF NOT EXISTS idx_buda_activo       ON buda_crypto(activo);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha      ON santander_gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria  ON santander_gastos(categoria);
CREATE INDEX IF NOT EXISTS idx_cuenta_fecha      ON santander_cuenta(fecha);
CREATE INDEX IF NOT EXISTS idx_ingresos_fecha    ON ingresos(fecha);
