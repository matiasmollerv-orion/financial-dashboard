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

# Paleta para gráficos de activos
ASSET_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
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
    </style>
    """, unsafe_allow_html=True)


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
    """Carga gastos Santander — paginación INLINE para evitar módulo cacheado en Streamlit Cloud."""
    data = _fetch_all_pages("santander_gastos")
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
