# ============================================================
# FINANCIAL DASHBOARD — ENTRY POINT
# Run: streamlit run dashboard/app.py
# ============================================================

import os
import sys

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

# ── Inyectar secrets: Streamlit Cloud primero, .env como fallback ─
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ.setdefault(k, v)
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuración de página ───────────────────────────────
st.set_page_config(
    page_title="Financial Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Importar utils (estilos) — reload para evitar caché de warm deploy ──
import importlib

# Forzar recarga de módulos clave para evitar versiones antiguas en warm deploys
for _mod_name in [
    "dashboard.utils",
    "dashboard.categorias",
    "dashboard.mappings",
]:
    try:
        import importlib, sys
        if _mod_name in sys.modules:
            importlib.reload(sys.modules[_mod_name])
    except Exception:
        pass

from dashboard.utils import apply_global_styles
apply_global_styles()


def _render_eye_toggle():
    """Toggle inline en app.py para evitar problema de módulo cacheado en warm deploy."""
    if "hide_amounts" not in st.session_state:
        st.session_state.hide_amounts = False
    label = "🙈 Ocultar montos" if not st.session_state.hide_amounts else "👁 Mostrar montos"
    if st.button(label, use_container_width=True, key="toggle_hide_amounts"):
        st.session_state.hide_amounts = not st.session_state.hide_amounts
        st.rerun()


def _render_eye_toggle():
    """Toggle inline en app.py para evitar problema de módulo cacheado en warm deploy."""
    if "hide_amounts" not in st.session_state:
        st.session_state.hide_amounts = False
    label = "🙈 Ocultar montos" if not st.session_state.hide_amounts else "👁 Mostrar montos"
    if st.button(label, use_container_width=True, key="toggle_hide_amounts"):
        st.session_state.hide_amounts = not st.session_state.hide_amounts
        st.rerun()

# ── Password protection ───────────────────────────────────
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

def check_password():
    """Retorna True si el usuario ingresó la contraseña correcta."""
    if not DASHBOARD_PASSWORD:
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Pantalla de login
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 💼 Financial Dashboard")
        st.markdown("---")
        pwd = st.text_input("Contraseña", type="password", key="pwd_input")
        if st.button("Ingresar", use_container_width=True):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    return False


if not check_password():
    st.stop()


# ── Sidebar de navegación ─────────────────────────────────
with st.sidebar:
    st.markdown("## 💼 Financial Dashboard")
    st.markdown("---")

    pagina = st.radio(
        "Navegación",
        options=[
            "📊 Resumen",
            "📈 Inversiones",
            "💳 Gastos",
            "📋 Estado de Resultados",
            "🔮 Proyecciones",
            "🔍 Inteligencia",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Toggle privacidad: ocultar/mostrar montos
    _render_eye_toggle()

    st.markdown("---")

    # Botón para limpiar cache
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache limpiado")

    st.markdown("---")
    st.caption("Datos actualizados al cargar la página (cache 5 min)")

    if DASHBOARD_PASSWORD:
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()


# ── Renderizar vista seleccionada ─────────────────────────
if pagina == "📊 Resumen":
    from dashboard.views.resumen import render
    render()

elif pagina == "📈 Inversiones":
    from dashboard.views.inversiones import render
    render()

elif pagina == "💳 Gastos":
    from dashboard.views.gastos import render
    render()

elif pagina == "📋 Estado de Resultados":
    from dashboard.views.eerr import render
    render()

elif pagina == "🔮 Proyecciones":
    from dashboard.views.proyecciones import render
    render()

elif pagina == "🔍 Inteligencia":
    from dashboard.views.intel import render
    render()
