-- Auto-auditoría del pipeline: cada corrida registra sus números
CREATE TABLE IF NOT EXISTS pipeline_stats (
  id BIGSERIAL PRIMARY KEY,
  fecha TIMESTAMPTZ DEFAULT NOW(),
  script TEXT NOT NULL,
  tabla_destino TEXT,
  filas_nuevas INTEGER,
  filas_totales_tabla INTEGER,
  duracion_seg NUMERIC,
  exit_ok BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_pipeline_stats_script_fecha ON pipeline_stats(script, fecha DESC);
