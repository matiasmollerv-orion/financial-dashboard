# ============================================================
# UTILIDADES COMPARTIDAS DEL DASHBOARD
# ============================================================

import pandas as pd
import streamlit as st

# ── FORMATOS ──────────────────────────────────────────────

def fmt_clp(v, decimals=0):
    """Formatea como pesos chilenos: $1.234.567"""
    try:
        v = float(v)
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "-"


def fmt_usd(v, decimals=2):
    """Formatea como dólares: USD 1,234.56"""
    try:
        v = float(v)
        sign = "-" if v < 0 else ""
        return f"{sign}USD {abs(v):,.{decimals}f}"
    except:
        return "-"


def fmt_pct(v, decimals=1):
    """Formatea como porcentaje: +12.3%"""
    try:
        v = float(v)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.{decimals}f}%"
    except:
        return "-"


def delta_color(v):
    """Retorna color según si es positivo o negativo."""
    try:
        return "green" if float(v) >= 0 else "red"
    except:
        return "gray"


# ── PRIVACY TOGGLE ────────────────────────────────────────

def amounts_hidden() -> bool:
    """Retorna True si el usuario activó ocultar montos."""
    import streamlit as st
    return st.session_state.get("hide_amounts", False)


def fmt_clp_safe(v, decimals=0) -> str:
    """fmt_clp() pero muestra '••••••' si hide_amounts está activo."""
    if amounts_hidden():
        return "••••••"
    return fmt_clp(v, decimals)


def fmt_usd_safe(v, decimals=2) -> str:
    """fmt_usd() pero muestra '••••••' si hide_amounts está activo."""
    if amounts_hidden():
        return "••••••"
    return fmt_usd(v, decimals)


def metric_safe(label: str, value, delta=None, delta_color_val: str = "normal", help: str = None):
    """st.metric() que oculta el valor si hide_amounts está activo."""
    import streamlit as st
    display_value = "••••••" if amounts_hidden() else value
    display_delta = None if amounts_hidden() else delta
    kwargs = {"label": label, "value": display_value}
    if display_delta is not None:
        kwargs["delta"] = display_delta
        kwargs["delta_color"] = delta_color_val
    if help:
        kwargs["help"] = help
    st.metric(**kwargs)


def render_eye_toggle():
    """Renderiza el botón 👁/🙈 en la sidebar para ocultar/mostrar montos."""
    import streamlit as st
    if "hide_amounts" not in st.session_state:
        st.session_state.hide_amounts = False
    label = "🙈 Ocultar montos" if not st.session_state.hide_amounts else "👁 Mostrar montos"
    if st.button(label, use_container_width=True, key="toggle_hide_amounts"):
        st.session_state.hide_amounts = not st.session_state.hide_amounts
        st.rerun()


# ── ESTILOS ───────────────────────────────────────────────

COLORS = {
    "primary": "#1f77b4",
    "green": "#2ecc71",
    "red": "#e74c3c",
    "yellow": "#f39c12",
    "gray": "#95a5a6",
    "bg": "#0e1117",
    "card": "#1e2130",
}

# Paleta para gráficos de activos (flat-UI original, sigue en uso en el
# resto del dashboard — no tocar para no romper vistas que ya la usan)
ASSET_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

# Paleta "metálica mate" (prototipo 2026-09) — 2 colores reales sacados
# pixel a pixel de la captura de referencia (verde, ámbar) + 14 derivados
# con la misma fórmula HSL (L~59-63%, S~46%; zona fría 170-300° un poco
# más clara para verse igual de "viva" que la cálida). ORDEN calculado
# por máxima separación de matiz (greedy furthest-point desde las 2
# anclas reales) — NO es orden estético, es orden de distinguibilidad:
# los primeros son los más distintos entre sí, así que un gráfico con
# pocas categorías (ej. "por tipo de activo", ~6) usa los mejores 6 solo
# tomando slice[:6]. Nunca reordenar ni saltar posiciones — el color es
# identidad, no ranking (ver skill dataviz/color-formula.md). Contraste
# vs fondo #11140F verificado uno a uno, todos >=4.6:1.
ASSET_COLORS_MATTE = [
    "#73BE8F",  # 1. verde       (real)      8.39:1
    "#D2AB5D",  # 2. ámbar       (real)      8.60:1
    "#9875CC",  # 3. púrpura                 5.09:1
    "#C76696",  # 4. rosa fuerte             5.10:1
    "#75B2CC",  # 5. celeste                 7.96:1
    "#9AC766",  # 6. lima                    9.49:1
    "#C76666",  # 7. rojo                    4.88:1
    "#BDC766",  # 8. oliva                  10.19:1
    "#76C766",  # 9. verde intenso           8.96:1
    "#75CCC6",  # 10. teal                   9.91:1
    "#7592CC",  # 11. azul                   5.96:1
    "#7875CC",  # 12. índigo                 4.61:1
    "#B875CC",  # 13. violeta                5.71:1
    "#C766BA",  # 14. magenta                5.34:1
    "#C78A66",  # 15. canela                 6.42:1
    "#C76673",  # 16. rojo rosado            4.93:1
]


def apply_global_styles():
    """Aplica CSS global al dashboard."""
    st.markdown("""
    <style>
        /* Métricas */
        [data-testid="metric-container"] {
            background-color: #1e2130;
            border: 1px solid #2d3250;
            border-radius: 10px;
            padding: 12px 16px;
        }
        [data-testid="metric-container"] label {
            font-size: 0.8rem !important;
            color: #8892b0 !important;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
            font-weight: 700 !important;
        }
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #131720;
        }
        /* Tablas */
        .dataframe { font-size: 0.85rem !important; }
        /* Títulos de sección */
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #ccd6f6;
            border-left: 3px solid #4e79a7;
            padding-left: 10px;
            margin: 20px 0 12px 0;
        }
        /* Cards */
        .info-card {
            background-color: #1e2130;
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 12px;
        }

        /* ── Stat cards (prototipo 2026-09) ──────────────────
           Tarjeta HTML propia, mismo look que st.metric pero con
           una 3ra línea de caption chica — cosa que st.metric no
           permite (solo label + value + delta).
           Paleta "metálica mate" sacada PIXEL A PIXEL de la captura
           de referencia de Matías (image-1789218865202.png), no a ojo:
             fondo      #11140F  (esquina + interior de tarjeta)
             valor      #EDEEE8  (blanco cálido)
             label      #70786B  (gris-sage apagado)
             caption    #9DA698  (gris-sage más claro)
             verde      #73BE8F  (real, +7.0% / +8.01%)
             ámbar txt  #EACF90  (real, texto dentro del callout)
             ámbar line #D2AB5D  (real, borde izquierdo del callout)
           Azul y rojo NO estaban en la captura (solo mostraba verde/
           ámbar) — derivados con la misma fórmula (HSL L~60%, S~50-55%)
           para que la familia se vea consistente. Contraste vs fondo
           verificado (todos >=5.6:1, boletín WCAG AA de sobra):
             azul  #6E9BCF  (6.40:1)
             rojo  #D37269  (5.64:1)
           No pude correr el validador CVD del skill (necesita node, no
           instalado acá) — mitigación: el signo +/- siempre va en el
           texto también, el color nunca es el único canal. */
        .stat-card {
            background-color: #11140F;
            border: 1px solid #262922;
            border-radius: 10px;
            padding: 14px 16px;
            height: 100%;
        }
        .stat-label {
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #70786B;
            margin-bottom: 6px;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #EDEEE8;
            font-variant-numeric: proportional-nums;
            line-height: 1.2;
        }
        .stat-delta {
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 2px;
        }
        .stat-delta.pos { color: #73BE8F; }
        .stat-delta.neg { color: #D37269; }
        .stat-delta.info { color: #6E9BCF; }
        .stat-delta.warn { color: #EACF90; }
        .stat-caption {
            font-size: 0.75rem;
            color: #9DA698;
            margin-top: 4px;
        }

        /* Callout — mismo fondo/borde reales de la captura. */
        .callout-box {
            background-color: #332B19;
            border-left: 3px solid #D2AB5D;
            border-radius: 6px;
            padding: 14px 18px;
            margin: 16px 0;
            font-size: 0.88rem;
            color: #EDEEE8;
            line-height: 1.5;
        }
        .callout-box b { color: #EACF90; }
        .callout-box .pos { color: #73BE8F; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)


def styled_metric(label: str, value, caption: str = None,
                  delta: str = None, delta_positive: bool = None):
    """
    Tarjeta de métrica en HTML propio (no st.metric) — mismo patrón visual
    pero con una línea de caption chica debajo, y sin la flecha ▲/▼ nativa
    de Streamlit (delta se pinta a mano con .pos/.neg).
    Respeta hide_amounts igual que metric_safe().
    """
    display_value = "••••••" if amounts_hidden() else value
    display_delta = None if amounts_hidden() else delta
    display_caption = None if amounts_hidden() else caption

    delta_html = ""
    if display_delta:
        cls = "pos" if delta_positive else ("neg" if delta_positive is False else "")
        delta_html = f'<div class="stat-delta {cls}">{display_delta}</div>'
    caption_html = f'<div class="stat-caption">{display_caption}</div>' if display_caption else ""

    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">{label}</div>
        <div class="stat-value">{display_value}</div>
        {delta_html}
        {caption_html}
    </div>
    """, unsafe_allow_html=True)


def callout(html_text: str):
    """Caja de nota destacada (borde ámbar). html_text acepta <b> para énfasis."""
    st.markdown(f'<div class="callout-box">{html_text}</div>', unsafe_allow_html=True)


def section_title(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


# ── CARGA CON CACHE ───────────────────────────────────────

def _get_sb():
    """Retorna cliente Supabase. Siempre importa get_client fresco para evitar módulo cacheado."""
    import sys, os, importlib
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import database.supabase_client as _sc
    importlib.reload(_sc)           # fuerza recarga del módulo en Streamlit Cloud (warm deploys)
    return _sc.get_client()


def _fetch_all_pages(table: str, order_col: str = "fecha", filters: dict = None,
                     page_size: int = 1000) -> list:
    """
    Paginación inline — NO depende de supabase_client._fetch_all para evitar
    que Streamlit Cloud use una versión cacheada del módulo.
    """
    sb = _get_sb()
    q = sb.table(table).select("*").order(order_col, desc=True)
    if filters:
        for col, (op, val) in filters.items():
            if op == "gte":
                q = q.gte(col, val)
            elif op == "lte":
                q = q.lte(col, val)
            elif op == "eq":
                q = q.eq(col, val)
    all_data, page = [], 0
    while True:
        start = page * page_size
        result = q.range(start, start + page_size - 1).execute()
        all_data.extend(result.data)
        if len(result.data) < page_size:
            break
        page += 1
    return all_data


@st.cache_data(ttl=300)
def load_cartera():
    """Carga cartera_actual desde Supabase."""
    sb = _get_sb()
    result = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(result.data)
    if df.empty:
        return df
    for col in ["precio_compra", "precio_actual", "cantidad"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_racional():
    """Carga transacciones Racional con monto_clp unificado (paginado)."""
    data = _fetch_all_pages("racional_transacciones")
    df = pd.DataFrame(data)
    if df.empty:
        return df
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    usd_clp = get_usd_clp()
    if "monto_clp" in df.columns and "monto_usd" in df.columns:
        df["monto_clp"] = pd.to_numeric(df["monto_clp"], errors="coerce")
        df["monto_usd"] = pd.to_numeric(df["monto_usd"], errors="coerce")
        df["monto_clp"] = df["monto_clp"].fillna(df["monto_usd"] * usd_clp)
    return df


@st.cache_data(ttl=300)
def load_buda():
    """Carga transacciones Buda crypto (paginado)."""
    data = _fetch_all_pages("buda_crypto")
    df = pd.DataFrame(data)
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_ingresos():
    """Carga ingresos."""
    sb = _get_sb()
    result = sb.table("ingresos").select("*").order("fecha", desc=True).execute()
    df = pd.DataFrame(result.data)
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_gastos():
    """Carga gastos tarjeta (Santander + Falabella CMR) — paginación INLINE
    para evitar módulo cacheado en Streamlit Cloud. La columna 'fuente'
    distingue el origen de cada fila (santander_tarjeta / falabella_tarjeta)."""
    data = _fetch_all_pages("santander_gastos") + _fetch_all_pages("falabella_gastos")
    df = pd.DataFrame(data)
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_cuenta():
    """Carga movimientos de cuenta corriente Santander."""
    data = _fetch_all_pages("santander_cuenta")
    df = pd.DataFrame(data)
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_vector():
    """Carga comprobantes Vector Capital."""
    sb = _get_sb()
    result = (sb.table("vector_capital_comprobantes").select("*")
              .eq("es_comision", True).order("fecha", desc=True).execute())
    df = pd.DataFrame(result.data)
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def get_usd_clp():
    """Retorna el tipo de cambio USD/CLP actual via yfinance (con fallback)."""
    try:
        import yfinance as yf
        fx = yf.download("USDCLP=X", period="5d", interval="1d", progress=False)
        if not fx.empty:
            import pandas as _pd
            val = fx["Close"].squeeze()
            if isinstance(val, _pd.DataFrame):
                val = val.iloc[:, 0]
            return float(val.iloc[-1])
    except Exception:
        pass
    return 901.76  # Fallback si yfinance falla
