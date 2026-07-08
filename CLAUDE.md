# Financial Dashboard — Contexto del Proyecto

## Deployment
- **Streamlit Cloud**: https://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/
- **GitHub**: https://github.com/matiasmollerv-orion/financial-dashboard (repo público, branch main)
- El dashboard en Streamlit Cloud se actualiza automáticamente con cada push a main
- Los secrets de Streamlit Cloud están configurados en el panel de Streamlit Cloud (no en .env)
- Si el dashboard no refleja cambios → limpiar caché: menú ☰ → "Clear cache"

## Automatización de datos
- **GitHub Actions**: `.github/workflows/daily-update.yml` — corre todos los días a las 8am Chile (11:00 UTC)
- **LaunchAgent macOS**: `com.financial.dashboard.weekly.plist` — corre todos los días a las 7am si el Mac está encendido
- La rutina principal es GitHub Actions (no depende del Mac)
- Secrets en GitHub Actions: SUPABASE_URL, SUPABASE_KEY, SANTANDER_PDF_PASSWORD, GMAIL_TOKEN_PICKLE, GMAIL_CREDENTIALS
- La rutina corre `--days 14` (modo incremental). El histórico se cargó manualmente una sola vez.

### ⚠️ Scripts que DEBEN correr diariamente (verificar al hacer cambios)
| Script | Tabla(s) | Qué carga |
|--------|----------|-----------|
| `load_santander.py --days 14` | `santander_gastos`, `santander_cuenta` | Tarjeta CLP/USD + cuenta corriente |
| `load_racional_ventas.py --days 14` | `racional_transacciones` (tipo=venta) | Ventas "Vendiste X (TICKER)" |
| `load_racional.py --days 14` | `racional_transacciones` (tipo=compra) | Compras "Invertiste en X (TICKER)" + portafolio nacional |
| `load_racional_pdf.py --days 14` | `racional_transacciones` | Transacciones desde PDFs DriveWealth (cubre DCA, rebalanceo, ventas no capturadas por emails individuales) |
| `load_buda.py --days 14` | `buda_crypto` | Compras programadas BTC/ETH |
| `intelligence/reconcile_notifications.py` | `santander_gastos` | Reconciliación notif iPhone vs PDF |
| `update_cartera.py` | `cartera_actual` | Aplica compras/ventas Racional+Buda sobre snapshot base y refresca precios via yfinance |

**TODOS estos pasos están en daily-update.yml con `continue-on-error: true`** — si uno falla, los demás siguen.

### ⚠️ cartera_actual NO es estática
- Base: snapshot manual al 2026-05-31 vía `cartera_base.py` (datos hardcoded)
- `update_cartera.py` lo lee y aplica todos los movimientos de `racional_transacciones` + `buda_crypto` posteriores al 2026-05-31
- Después refresca precios con yfinance (incluyendo `.SN` para Chile y `-USD` para crypto)
- NUNCA editar `cartera_base.py` para "actualizar" a diario — solo modificarlo al cierre de mes con nueva cartola PDF; los movimientos se aplican automáticamente
- Santander Corredora stocks usan sufijo `_STG` (ENELCHILE_STG, ENJOY_STG, LTM_STG) para distinguir de posiciones Racional
- Nacional: incluye 20 stocks Racional + 3 Santander Corredora (ENELCHILE_STG, ENJOY_STG, LTM_STG) + fondos (CFMITNIPSA)
- Internacional: 65 posiciones exactas del PDF DriveWealth (8 decimales)
- Crypto: BTC y ETH con cantidades base; Buda compras se acumulan automáticamente

**NO automatizado (carga manual ocasional):**
- `load_to_supabase.py` → Vector Capital (vector_capital_comprobantes) — comprobantes esporádicos

## Estructura del proyecto
```
dashboard/
  app.py              ← entry point Streamlit
  utils.py            ← fmt_clp, fmt_usd, fmt_pct, load_* con cache
  categorias.py       ← 5 niveles de categorización de gastos
  mappings.py         ← get_tipo(), get_pais(), get_sector() por ticker
  views/
    resumen.py        ← Resumen patrimonial
    inversiones.py    ← 5 tabs: Consolidado, Chile, Internacional, Historial, Fundamentos
    gastos.py         ← Gastos Santander con categorización, drill-down y alertas
    eerr.py           ← Estado de Resultados mensual
    proyecciones.py   ← Proyecciones patrimoniales
    intel.py          ← 🔍 Inteligencia: Daily Brief + alertas cartera + feed AI
database/
  supabase_client.py  ← cliente Supabase, paginación automática
extractors/
  santander_pdf.py    ← parser PDFs Santander (tarjeta + cuenta corriente)
  buda_email.py       ← parser compras programadas BTC/ETH
  racional_email.py   ← parser compras/ventas Racional
intelligence/
  schema.sql          ← SQL para crear tablas market_news, market_intelligence, portfolio_alerts
  config/
    investor_profile.yaml ← PERFIL: horizontes, límites de riesgo, liquidez emprendimiento, profit taking, eventos
    watchlist.yaml    ← Fuente de verdad: 25 recurrentes, watchlist tiers, entry targets, buckets, 13F, pendientes
    rules.yaml        ← Reglas Connors DIP + z-score gating + RSI(2) + filtros globales
  news_fetcher.py     ← RSS → market_news (cartera + watchlist tickers + bucket keywords)
  market_regime.py    ← v1: risk-on/neutral/risk-off — FRED sin key (HY spread, curva) + SPY/SMA200 + VIX. Modula sizing y sugerencias
  opportunity_detector.py ← v4: dips z-score + RSI(2) + gate fundamental anti-cuchillo (yfinance) + SIZING POR RIESGO (monto = 0.25% portafolio / σ mensual del ticker, no montos fijos) + régimen + score 0-100 + target drift (lunes)
  sell_engine.py      ← v2: SEÑALES DE VENTA — concentración >12%, trailing 2σ, EVALUAR al duplicar, eventos, liquidez, factor-cluster (lunes: posiciones con corr>0.6 = una apuesta; excluye ETFs core del clustering)
  edgar_monitor.py    ← v1: SEC EDGAR — Form 4 insider buys/clusters, 8-K materiales, 13F smart money diff
  earnings_radar.py   ← v1: aviso 5 días ANTES de earnings de posiciones grandes + tier1
  alert_outcomes.py   ← v1: feedback loop — retorno forward +5/20/60d en metricas de cada alerta; --scorecard
  gbrain_bridge.py    ← v1: SOLO LOCAL (LaunchAgent) — newsletters GBrain → market_news; alertas → brain
  backtest_rules.py   ← v1: backtest ad-hoc de reglas dip/RSI2 vs baseline (NO en workflow)
  ai_analyst.py       ← v2: Claude analiza noticias (DESACTIVADO en workflow por costo API)
  daily_brief.py      ← v2: Max 5 alertas accionables (DESACTIVADO en workflow por costo API)
  report_builder.py   ← v2: Email limpio con alert cards + fallback a alertas crudas sin AI
  portfolio_health.py ← análisis independiente de cartera (concentración, drawdown, etc.)
load_santander.py     ← carga PDFs Santander a Supabase
load_racional_ventas.py ← carga ventas Racional
load_racional.py      ← carga compras Racional
load_buda.py          ← carga compras crypto Buda
```

## Base de datos (Supabase)
Tablas principales:
- `santander_gastos`: gastos tarjeta de crédito (CLP y USD)
- `santander_cuenta`: movimientos cuenta corriente
- `racional_transacciones`: compras y ventas en Racional (internacional y nacional)
- `cartera_actual`: posiciones actuales del portafolio
- `buda_crypto`: transacciones crypto en Buda
- `ingresos`: ingresos manuales registrados
- `vector_capital_comprobantes`: comprobantes Vector Capital

Tablas de inteligencia de mercado (ver `intelligence/schema.sql`):
- `market_news`: noticias crudas filtradas por keyword match con cartera
- `market_intelligence`: análisis AI de cada noticia (Claude Haiku)
- `portfolio_alerts`: alertas independientes de cartera (concentración, drawdown, etc.)
  - Categoría especial `daily_brief` guarda el resumen ejecutivo diario

## ⚠️ REGLAS CRÍTICAS — NO OLVIDAR

### Paginación Supabase — CRÍTICO
Supabase tiene un límite de 1000 filas por query. Se necesita paginación.

**PROBLEMA IMPORTANTE**: Streamlit Cloud usa "warm deployments" — el proceso Python
NO se reinicia, entonces `sys.modules` puede tener versiones ANTIGUAS de módulos
importados. Nunca usar `from database.supabase_client import _fetch_all` en funciones
cacheadas, porque puede ejecutar la versión antigua sin paginación.

**SOLUCIÓN**: La paginación está INLINE en `utils.py` con `importlib.reload()`:
```python
def _get_sb():
    import importlib
    import database.supabase_client as _sc
    importlib.reload(_sc)  # fuerza recarga del módulo
    return _sc.get_client()

def _fetch_all_pages(table, order_col="fecha", page_size=1000):
    sb = _get_sb()
    q = sb.table(table).select("*").order(order_col, desc=True)
    all_data, page = [], 0
    while True:
        r = q.range(page * page_size, page * page_size + page_size - 1).execute()
        all_data.extend(r.data)
        if len(r.data) < page_size: break
        page += 1
    return all_data
```
SIN esto, el dashboard muestra solo ~11 meses de datos (1000 filas más recientes).
Tablas que requieren paginación: `santander_gastos` (7539 filas), `racional_transacciones`, `buda_crypto`.

### Formato moneda: SIEMPRE usar fmt_clp()
- Pesos chilenos: `fmt_clp(v)` → `$1.234.567` (puntos como miles, sin decimales)
- Dólares: `fmt_usd(v, 2)` → `USD 1,234.56`
- Porcentaje: `fmt_pct(v)` → `+12.3%`
- En Plotly hover templates: usar customdata pre-formateado, NO `%{y:,.0f}` (eso es formato US)
- Ejemplo correcto:
  ```python
  df["monto_fmt"] = df["monto"].apply(fmt_clp)
  fig.update_traces(
      customdata=df[["monto_fmt"]].values,
      hovertemplate="<b>%{x}</b><br>%{customdata[0]}<extra></extra>"
  )
  ```

### yfinance para acciones chilenas
Las acciones de la Bolsa de Santiago necesitan sufijo `.SN`:
- `BCI` → `BCI.SN`, `LTM` → `LTM.SN`, `CENCOSUD` → `CENCOSUD.SN`
- Código en inversiones.py:
  ```python
  yf_map = {
      row["ticker"]: f"{row['ticker']}.SN" if row.get("mercado") == "nacional" else row["ticker"]
      for _, row in df_f.drop_duplicates("ticker").iterrows()
  }
  yf_tickers = tuple(sorted(set(yf_map.values())))
  metrics = _fetch_metrics(yf_tickers)  # retorna ticker sin .SN para merge
  ```
- `_fetch_metrics` ya hace el strip del .SN internamente antes de retornar

### Categorización de gastos
- 5 niveles: Savings, Investments, Impuestos, Fixed Costs, Guilt Free
- Default sin match: `("Sin Categorizar", "Otros")` — NUNCA Guilt Free
- MONTO CANCELADO y TRASPASO A DEUDA NACIONAL → Fixed Costs / Pago TC (son pagos de TC, NO gastos reales)
- La subcategoría "Pago TC" se EXCLUYE de todos los análisis de gastos (está en EXCLUIR_SUBS)
- Si algo aparece como "Sin Categorizar" con monto alto, agregar patrón a `categorias.py`
- Patrones clave ya definidos:
  - `MONTO CANCELADO` → Fixed Costs / Pago TC
  - `TRASPASO A DEUDA NACIONAL` → Fixed Costs / Pago TC
  - `NOTA DE CREDITO` → Fixed Costs / Comisiones
  - `FULLTENNIS`, `CLUB VITACURA`, `NAVKA` → Guilt Free / Deportes/Bienestar
  - `PASAJEBUS` → Fixed Costs / Transporte
  - `EL TORO`, `DA DINO`, `CHIRINGO` → Guilt Free / Restoran/Social
  - `ASICS` → Guilt Free / For me
  - `KITCHEN CENTER`, `INCHCAPE` → Guilt Free / Compras
  - `MP*ENTELHOGAR` → Fixed Costs / Servicios

### Secrets Streamlit Cloud
Usar `_get_secret()` que intenta `st.secrets` primero, luego `.env`:
```python
def _get_secret(key: str) -> str:
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val: return val
    except Exception:
        pass
    return os.getenv(key)
```
`python-dotenv` solo funciona en local, NO en Streamlit Cloud.

### Parser cuenta corriente PDF
- Usa `pdfplumber` con `page.extract_words()` y posiciones X
- Columnas por posición X: CARGO (380-450), ABONO (450-545), SALDO (>545)
- Los PDFs `_CC.pdf` son cuenta corriente, los demás son tarjeta de crédito
- El año se extrae del header del PDF

### Exclusiones en análisis de gastos
En `gastos.py` y `eerr.py`:
```python
EXCLUIR_TOP  = ["Investments"]
EXCLUIR_SUBS = ["Pago TC"]
df_gastos = df[
    ~df["top_level"].isin(EXCLUIR_TOP) &
    ~df["subcategoria"].isin(EXCLUIR_SUBS)
]
```

## Fuentes de datos
- **Santander**: PDFs desde Gmail (from:mensajeria@santander.cl)
  - Tarjeta CLP y USD → `santander_gastos`
  - Cuenta corriente `_CC.pdf` → `santander_cuenta`
- **Racional**: emails con subject "Compraste X" / "Vendiste X"
- **Gmail OAuth**: token.pickle en config/ (binario, NO json)

## Heatmaps en inversiones
```python
# IMPORTANTE: el gris (0%) mapea a posición 0.40 en el rango [-40,60]
# porque (0 - (-40)) / (60 - (-40)) = 40/100 = 0.40
# Si el gris está en 0.50, los tickers con 0% aparecen rojo → INCORRECTO
HEAT_SCALE = [
    [0.00, "#8b0000"],   # -40%
    [0.25, "#e74c3c"],   # -10%
    [0.40, "#e8e8e8"],   #   0% ← debe coincidir con (0-min)/(max-min)
    [0.58, "#2ecc71"],   # +11%
    [1.00, "#1a6b35"],   # +60%
]
HEAT_RANGE = [-40, 60]
```
Si cambias HEAT_RANGE, recalcula la posición del gris: `pos_gris = (0 - min) / (max - min)`

## Tab Fundamentos (inversiones.py)
- Filtros: Tipo, País, Sector/Industria
- Gráfico burbuja: P/E (x) vs EPS (y), tamaño = valor cartera, color = sector
- Líneas de referencia P/E: 15x (verde, barato) y 25x (rojo, caro)
- Barra comparativa P/E coloreada: verde <15, amarillo 15-25, rojo >25
- Tabla con todas las métricas incluyendo sector

## Alertas de gastos (gastos.py)
1. Duplicados: mismo (descripcion, monto) en la misma semana
2. Outliers: monto > Q3 + 3×IQR por subcategoría (mín. 4 transacciones)
3. Sin categorizar > $30.000
4. Cobros en USD en tarjeta nacional

## Sistema de Alertas v2 (intelligence/)
Pipeline diario: news_fetcher → ai_analyst → opportunity_detector → daily_brief → report_builder → email_sender

### Filosofia
- MAX 5 alertas por email. Menos es mejor.
- Una alerta NO es estar en rojo en una posicion (eso es ruido).
- Una alerta SI es: oportunidad de compra (DIP), entry target alcanzado, noticia que crea oportunidad, accion pendiente urgente.
- Prioridad: oportunidades > riesgos.

### watchlist.yaml — Fuente de verdad
- 25 tickers recurrentes (DCA semanal ~USD 1,802/mes)
- Watchlist Tier 1 (entry targets definidos), Tier 2 (triggers), Tier 3 (seguimiento)
- Acciones pendientes con urgencia
- Buckets tematicos con keywords para cross-reference con noticias
- Smart money funds (15) con CIK para 13F tracking
- Conferencias tech con calendario
- ETFs core que NUNCA alertan
- Sincronizar con CONTEXT.md cuando cambie el plan

### Flujo de alertas (workflow activo — sin costo API)
1. `news_fetcher`: noticias RSS para cartera + watchlist + bucket keywords
2. `opportunity_detector`: dips z-score + RSI(2) + entry targets + tier triggers + score compuesto (técnica × informacional × convicción), cap top 15
3. `sell_engine`: concentración >12%, trailing 2σ, EVALUAR al duplicar, eventos (lockups), liquidez emprendimiento
4. `edgar_monitor`: Form 4 insider buys/clusters + 8-K materiales + 13F smart money (detección temprana pre-precio)
5. `earnings_radar`: aviso 5 días antes de earnings
6. `alert_outcomes`: registra retornos forward de cada alerta (feedback loop; `--scorecard` para calibración)
7. `report_builder` + `email_sender`: email diario

LOCAL (LaunchAgent 7am, run_weekly_update.sh): `gbrain_bridge` — newsletters del brain → market_news (alimenta el score compuesto) y alertas activas → página finanzas/alertas-sistema del brain.

### 🩺 Auto-auditoría del pipeline (detecta fallas silenciosas)
- Tabla `pipeline_stats`: cada paso del workflow va envuelto en
  `python -m intelligence.pipeline_stats --script X --table Y -- <comando>`
  → registra filas nuevas (delta count=exact, inmune al límite 1000), duración, exit_ok.
  El wrapper PROPAGA el exit code (failure tracker sigue funcionando).
- `health_check.py` (workflow health-check.yml 9:30am) compara cada script contra
  su PROPIO historial (~4 semanas): exit_ok=false, cadencia autoderivada (0 filas
  en >3× su intervalo histórico), caída >60% vs promedio, tabla estancada.
  Mínimo 4 registros antes de alertar (sin falsos positivos la primera semana).
- Anomalías → portfolio_alerts categoria=pipeline_health → sección 🩺 del email
  diario (solo aparece si hay problemas).
- DDL: migración en supabase/migrations/ aplicada via `supabase db push` (CLI linkeado).
- Antecedente: el bug de paginación Supabase (solo 1000 filas) estuvo meses invisible
  porque nada comparaba lo cargado contra lo esperado.

### ⚠️ Deduplicación email vs PDF DriveWealth (bug conocido)
Los trades pueden llegar por DOS fuentes: email "Invertiste en" (trade completo) y
PDF DriveWealth (fills partidos, ej 1.024125 → 1.0 + 0.024125). La dedupe por
(fecha, ticker, monto) NO los matchea → posiciones infladas. El snapshot mensual
desde cartolas oficiales LIMPIA esta contaminación (por eso es crítico hacerlo
cada cierre de mes). En junio 2026 infló AVGO +2.03, MRVL +1.73, NU +6.49, NVDA +0.39.

(`ai_analyst` y `daily_brief` existen pero están FUERA del workflow por costo API ~$54/mes)

### Backtest (validación con datos reales, jul 2026, universo propio 2y)
- medium_dip: +25.8% a 20d vs +5.2% baseline (75% hit) — regla más valiosa, rara
- large_dip: +11.0% a 20d — rara y valiosa
- small_dip: edge de corto plazo (+4.6% a 5d), se diluye a 20d
- rsi2: 199 señales, 64% hit, edge modesto consistente
- Correr `python -m intelligence.backtest_rules` tras cambiar umbrales

### investor_profile.yaml — Perfil del inversor (gobierna todas las alertas)
- Emprendimiento: 20-30% del portafolio tocable en 1-2 años → debe estar en activos líquidos/estables
- Límites: máx 12% por posición individual (ex ETFs core), máx 25% por bucket
- Cash oportunístico: USD 500-1.000/mes además del DCA
- Profit taking: modo "evaluar_con_contexto" (NO trims mecánicos) + trailing guardrail 2σ en especulativas
- Clasificación de horizonte: core (20y) / conviccion (5-10y) / satelite (3-7y) / especulativo (2-5y)
- Eventos programados con fecha (ej. lockup VCX sept 2026)

## Python
- venv en `venv/` con Python 3.9 (pendiente migrar a 3.12)
- Dependencias en requirements.txt

## Notas históricas importantes
- El histórico de gastos (2019-2026) se cargó manualmente. La rutina diaria solo carga --days 14.
- Deduplicación por (fecha, descripcion, monto, moneda) antes de insertar
- Parser cuenta corriente usa posiciones X de palabras, no regex (PDFs tienen texto posicional)
- Sin paginación en Supabase, dashboard mostraba solo ~1000 filas = apenas ~11 meses de datos
