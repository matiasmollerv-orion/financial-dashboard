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

## Estructura del proyecto
```
dashboard/
  app.py              ← entry point Streamlit
  utils.py            ← fmt_clp, fmt_usd, fmt_pct, load_* con cache
  categorias.py       ← 5 niveles de categorización de gastos
  categorias_test.py  ← tests de categorización (si existe)
  mappings.py         ← get_tipo(), get_pais(), get_sector() por ticker
  views/
    resumen.py        ← Resumen patrimonial
    inversiones.py    ← 5 tabs: Consolidado, Chile, Internacional, Historial, Fundamentos
    gastos.py         ← Gastos Santander con categorización, drill-down y alertas
    eerr.py           ← Estado de Resultados mensual
    proyecciones.py   ← Proyecciones patrimoniales
database/
  supabase_client.py  ← cliente Supabase, paginación automática
extractors/
  santander_pdf.py    ← parser PDFs Santander (tarjeta + cuenta corriente)
scripts/
  load_santander.py   ← carga PDFs Santander a Supabase
  load_racional_ventas.py ← carga emails Racional
```

## Base de datos (Supabase)
Tablas principales:
- `santander_gastos`: gastos tarjeta de crédito (CLP y USD), 7.539+ filas 2019–2026
- `santander_cuenta`: movimientos cuenta corriente
- `racional_transacciones`: compras y ventas en Racional (internacional y nacional)
- `cartera_actual`: posiciones actuales del portafolio
- `buda_crypto`: transacciones crypto en Buda
- `ingresos`: ingresos manuales registrados
- `vector_capital_comprobantes`: comprobantes Vector Capital

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

## Python
- venv en `venv/` con Python 3.9 (pendiente migrar a 3.12)
- Dependencias en requirements.txt

## Notas históricas importantes
- El histórico de gastos (2019-2026) se cargó manualmente. La rutina diaria solo carga --days 14.
- Deduplicación por (fecha, descripcion, monto, moneda) antes de insertar
- Parser cuenta corriente usa posiciones X de palabras, no regex (PDFs tienen texto posicional)
- Sin paginación en Supabase, dashboard mostraba solo ~1000 filas = apenas ~11 meses de datos
