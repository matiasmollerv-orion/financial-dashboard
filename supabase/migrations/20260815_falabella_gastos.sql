-- Nueva fuente de gastos: tarjeta de crédito CMR Falabella (Cliente Elite).
-- Mismo esquema que santander_gastos para poder unirlas en el dashboard
-- sin lógica especial (utils.py hace UNION por columna 'fuente').
CREATE TABLE IF NOT EXISTS public.falabella_gastos (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    descripcion TEXT NOT NULL,
    monto NUMERIC NOT NULL,
    moneda TEXT DEFAULT 'CLP',
    categoria TEXT,
    fuente TEXT DEFAULT 'falabella_tarjeta',
    archivo TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_falabella_gastos_fecha ON public.falabella_gastos(fecha);

-- Defensa en profundidad, mismo criterio que la migración RLS anterior:
-- todo el proyecto usa la key service_role (bypasea RLS), así que esto
-- no cambia el comportamiento de GitHub Actions ni Streamlit.
ALTER TABLE public.falabella_gastos ENABLE ROW LEVEL SECURITY;
