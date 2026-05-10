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

@st.cache_data(ttl=300)
def load_cartera():
    """Carga cartera_actual desde Supabase."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_client
    sb = get_client()
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
    """Carga transacciones Racional."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_racional_transacciones
    df = get_racional_transacciones()
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_buda():
    """Carga transacciones Buda crypto."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_buda_crypto
    df = get_buda_crypto()
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_ingresos():
    """Carga ingresos."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_ingresos
    df = get_ingresos()
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_gastos():
    """Carga gastos Santander."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_gastos
    df = get_gastos()
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


@st.cache_data(ttl=300)
def load_vector():
    """Carga comprobantes Vector Capital."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.supabase_client import get_comisiones
    df = get_comisiones()
    if not df.empty and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def get_usd_clp():
    """Retorna el tipo de cambio USD/CLP guardado."""
    return 901.76  # Actualizar manualmente o via API
