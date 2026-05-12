# Financial Dashboard — Contexto del Proyecto

## Deployment
- **Streamlit Cloud**: https://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/
- **GitHub**: https://github.com/matiasmollerv-orion/financial-dashboard (repo público, branch main)
- El dashboard en Streamlit Cloud se actualiza automáticamente con cada push a main
- Los secrets de Streamlit Cloud están configurados en el panel de Streamlit Cloud (no en .env)

## Automatización de datos
- **GitHub Actions**: `.github/workflows/daily-update.yml` — corre todos los días a las 8am Chile (11:00 UTC)
- **LaunchAgent macOS**: `com.financial.dashboard.weekly.plist` — corre todos los días a las 7am si el Mac está encendido
- La rutina principal es GitHub Actions (no depende del Mac)
- Secrets en GitHub Actions: SUPABASE_URL, SUPABASE_KEY, SANTANDER_PDF_PASSWORD, GMAIL_TOKEN_PICKLE, GMAIL_CREDENTIALS

## Estructura de datos
- **Supabase** como base de datos
- Tablas principales:
  - `santander_gastos`: gastos tarjeta de crédito (CLP y USD)
  - `santander_cuenta`: movimientos cuenta corriente
  - `racional_transacciones`: compras y ventas en Racional (internacional)
  - `portfolio` o similar: cartera actual de inversiones

## Fuentes de datos
- **Santander**: PDFs de estados de cuenta descargados desde Gmail (from:mensajeria@santander.cl)
  - Tarjeta de crédito CLP y USD
  - Cartola cuenta corriente (archivos terminan en _CC.pdf)
- **Racional**: emails de Gmail con subject "Compraste X (TICKER)" y "Vendiste X (TICKER)"
- **Gmail OAuth**: token.pickle en config/ (pickle binario, NO json)

## Categorización de gastos
- 5 niveles top-level: Savings, Investments, Impuestos, Fixed Costs, Guilt Free
- Sin match → "Sin Categorizar / Otros" (NO Guilt Free)
- Archivo: `dashboard/categorias.py`

## Dashboard (Streamlit)
- Entry point: `dashboard/app.py`
- Vistas en `dashboard/views/`: resumen.py, gastos.py, inversiones.py, eerr.py, proyecciones.py
- inversiones.py tiene 5 tabs: Consolidado, Acciones Chile, Internacional, Historial Racional, Fundamentos
- Tab Fundamentos: métricas P/E, EPS, Dividend Yield via yfinance (cache 4h)
- Heatmaps: escala rojo oscuro → gris (0%) → verde oscuro, rango fijo -40% a +60%

## Python
- venv en `venv/` con Python 3.9 (pendiente migrar a 3.12)
- Dependencias en requirements.txt
- Scripts de carga: load_santander.py, load_racional_ventas.py, load_racional.py (si existe)
- Todos soportan --days N para modo incremental

## Notas importantes
- load_santander.py deduplica por (fecha, descripcion, monto, moneda) antes de insertar
- Parser cuenta corriente usa posiciones X de palabras en PDF (no regex sobre texto plano)
- Los PDFs de Santander están en data/raw/santander/ (no se suben a GitHub por .gitignore)
- Deduplicación de Supabase tiene bug de paginación: solo compara contra los primeros 1000 registros (pendiente fix)
