# ============================================================
# VISTA: INTELIGENCIA DE MERCADO
# Daily Brief + alertas de cartera + feed de noticias analizadas
# ============================================================

from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from dashboard.utils import (
    fmt_clp, fmt_pct, fmt_clp_safe, metric_safe, amounts_hidden,
    section_title,
)
from database.supabase_client import get_client


# Colores por tipo/severidad
SEV_COLOR = {
    "critica": "#8b0000", "alta": "#e74c3c", "media": "#f39c12",
    "baja":    "#3498db", "info": "#95a5a6",
}
TIPO_COLOR = {
    "riesgo":      "#e74c3c",
    "oportunidad": "#2ecc71",
    "neutro":      "#95a5a6",
}
CONF_ICON = {
    "alta":  "🟢", "media": "🟡", "baja":  "🟠", "ruido": "⬛",
}


# ── LOADERS CACHEADOS ────────────────────────────────────────
@st.cache_data(ttl=120)
def load_daily_brief() -> str:
    """El último daily brief (categoria='daily_brief')."""
    sb = get_client()
    r = (sb.table("portfolio_alerts")
           .select("mensaje,fecha_alerta")
           .eq("categoria", "daily_brief")
           .order("fecha_alerta", desc=True)
           .limit(1)
           .execute())
    return (r.data[0]["mensaje"] if r.data else "")


@st.cache_data(ttl=120)
def load_alerts() -> pd.DataFrame:
    sb = get_client()
    r = (sb.table("portfolio_alerts")
           .select("*")
           .neq("categoria", "daily_brief")
           .eq("activo_alerta", True)
           .order("fecha_alerta", desc=True)
           .limit(200)
           .execute())
    return pd.DataFrame(r.data)


@st.cache_data(ttl=120)
def load_intelligence(hours: int = 48) -> pd.DataFrame:
    """Análisis AI con datos de noticias (join)."""
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    # Hacemos dos queries y mergemos en pandas (más simple que un JOIN)
    intel = (sb.table("market_intelligence").select("*")
               .gte("fecha_analisis", cutoff)
               .order("relevancia_pct", desc=True).execute())
    if not intel.data:
        return pd.DataFrame()
    df_i = pd.DataFrame(intel.data)

    noticias_ids = df_i["noticia_id"].dropna().unique().tolist()
    if not noticias_ids:
        return df_i

    nots = (sb.table("market_news").select("id,titulo,resumen,url,fuente,fecha_noticia")
              .in_("id", noticias_ids).execute())
    df_n = pd.DataFrame(nots.data) if nots.data else pd.DataFrame()
    if df_n.empty:
        return df_i

    df_n = df_n.rename(columns={"id": "noticia_id"})
    df = df_i.merge(df_n, on="noticia_id", how="left")
    return df


@st.cache_data(ttl=300)
def load_recent_news(hours: int = 24, limit: int = 50) -> pd.DataFrame:
    """Noticias crudas (no analizadas) recientes."""
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    r = (sb.table("market_news").select("*")
           .gte("fecha_noticia", cutoff)
           .order("relevancia_preliminar", desc=True)
           .order("fecha_noticia", desc=True)
           .limit(limit).execute())
    return pd.DataFrame(r.data)


# ── HELPERS UI ───────────────────────────────────────────────
def color_tipo(t: str) -> str:
    return TIPO_COLOR.get((t or "").lower(), "#888")


def render_alert_card(row: pd.Series):
    sev = (row.get("severidad") or "info").lower()
    color = SEV_COLOR.get(sev, "#888")
    cat = (row.get("categoria") or "").upper()
    activo = row.get("activo") or "—"
    titulo = row.get("titulo") or ""

    metricas = row.get("metricas") or {}
    if isinstance(metricas, str):
        try:
            import json
            metricas = json.loads(metricas)
        except Exception:
            metricas = {}

    st.markdown(
        f"""
<div style="border-left: 4px solid {color}; background:#1e2130; padding:10px 14px; border-radius:6px; margin-bottom:8px;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <strong style="color:#ccd6f6;">{titulo}</strong>
    <span style="background:{color}22; color:{color}; padding:2px 8px; border-radius:10px; font-size:0.75rem;">
      {sev.upper()} · {cat}
    </span>
  </div>
  <div style="color:#a0aec0; font-size:0.85rem; margin-top:4px;">{row.get('mensaje','')}</div>
  <div style="color:#8892b0; font-size:0.8rem; margin-top:6px;">💡 {row.get('sugerencia','')}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_news_card(row: pd.Series):
    tipo = (row.get("tipo") or "neutro").lower()
    color = color_tipo(tipo)
    icon = CONF_ICON.get((row.get("confianza_senal") or "").lower(), "⚪")
    rel = row.get("relevancia_pct") or 0
    horiz = row.get("horizonte") or ""
    titulo = row.get("titulo") or "(sin título)"
    fuente = row.get("fuente") or ""
    fecha = row.get("fecha_noticia") or ""
    if fecha:
        try:
            fecha = pd.to_datetime(fecha).strftime("%d/%m %H:%M")
        except Exception:
            pass
    resumen = row.get("resumen_esp") or ""
    razonamiento = row.get("razonamiento") or ""
    contra = row.get("contraargumento") or ""
    accion = row.get("accion_sugerida") or ""
    tickers = row.get("tickers_afectados") or []
    if isinstance(tickers, str):
        tickers = tickers.strip("{}").split(",") if tickers else []
    tickers_str = ", ".join(t.strip() for t in tickers if t.strip())
    url = row.get("url") or ""

    badge = f"<span style='background:{color}22; color:{color}; padding:2px 8px; border-radius:10px; font-size:0.75rem;'>{tipo.upper()}</span>"
    rel_bar = "█" * min(int(rel/10), 10) + "░" * (10 - min(int(rel/10), 10))

    with st.container():
        st.markdown(
            f"""
<div style="border-left: 4px solid {color}; background:#1e2130; padding:12px 14px; border-radius:6px; margin-bottom:10px;">
  <div style="display:flex; justify-content:space-between; align-items:start; gap:10px;">
    <strong style="color:#ccd6f6; flex:1;">{icon} {titulo}</strong>
    {badge}
  </div>
  <div style="color:#8892b0; font-size:0.75rem; margin-top:2px;">
    📰 {fuente} · 📅 {fecha} · 🎯 relev: {rel} <span style="font-family:monospace;">{rel_bar}</span> · ⏰ {horiz}
  </div>
  <div style="color:#a0aec0; font-size:0.9rem; margin-top:8px;">{resumen}</div>
""",
            unsafe_allow_html=True,
        )

        if tickers_str:
            st.caption(f"📌 Afecta: **{tickers_str}**")

        with st.expander("Ver análisis completo"):
            if razonamiento:
                st.markdown(f"**🔍 Razonamiento:** {razonamiento}")
            if contra:
                st.markdown(f"**⚖️ Contraargumento:** {contra}")
            if accion:
                st.markdown(f"**🎯 Acción sugerida:** {accion}")
            if url:
                st.markdown(f"[🔗 Ver noticia original]({url})")

        st.markdown("</div>", unsafe_allow_html=True)


# ── RENDER PRINCIPAL ─────────────────────────────────────────
def render():
    st.title("🔍 Inteligencia de Mercado")

    # Estado de servicios
    try:
        sb = get_client()
        n_news = sb.table("market_news").select("id", count="exact").execute().count
        n_intel = sb.table("market_intelligence").select("id", count="exact").execute().count
        n_alerts = sb.table("portfolio_alerts").select("id", count="exact").eq("activo_alerta", True).execute().count
    except Exception as e:
        st.error(f"❌ Las tablas de inteligencia no existen aún. Corre el SQL en `intelligence/schema.sql` en Supabase.")
        st.code(open("intelligence/schema.sql").read() if False else "Ver archivo intelligence/schema.sql", language="sql")
        return

    col1, col2, col3 = st.columns(3)
    with col1: st.metric("📰 Noticias en BD", n_news)
    with col2: st.metric("🧠 Analizadas por AI", n_intel)
    with col3: st.metric("⚠️ Alertas activas", n_alerts)

    st.divider()

    # ── DAILY BRIEF ──────────────────────────────────────────
    section_title("🌅 Daily Brief")
    brief = load_daily_brief()
    if brief:
        with st.container():
            st.markdown(
                f"<div style='background:#1e2130; padding:18px 22px; border-radius:10px; border-left: 4px solid #4e79a7;'>{brief}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("Aún no hay Daily Brief. Se genera con `python -m intelligence.daily_brief` (requiere ANTHROPIC_API_KEY).")

    st.divider()

    # ── ALERTAS DE CARTERA ───────────────────────────────────
    section_title("⚠️ Alertas activas de cartera")
    df_alerts = load_alerts()

    if df_alerts.empty:
        st.success("✅ No hay alertas activas. Tu cartera no tiene riesgos automáticos detectados.")
    else:
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            sev_filter = st.multiselect(
                "Severidad",
                options=["critica", "alta", "media", "baja", "info"],
                default=["critica", "alta", "media"],
                key="alert_sev",
            )
        with col_f2:
            cat_filter = st.multiselect(
                "Categoría",
                options=sorted(df_alerts["categoria"].dropna().unique().tolist()),
                default=sorted(df_alerts["categoria"].dropna().unique().tolist()),
                key="alert_cat",
            )

        df_f = df_alerts[
            df_alerts["severidad"].isin(sev_filter) &
            df_alerts["categoria"].isin(cat_filter)
        ]

        if df_f.empty:
            st.info("Sin alertas con esos filtros.")
        else:
            # Resumen contadores
            sev_counts = df_f["severidad"].value_counts()
            cols = st.columns(len(sev_counts) or 1)
            for i, (s, c) in enumerate(sev_counts.items()):
                with cols[i]:
                    st.metric(s.capitalize(), c)

            # Cards
            for _, row in df_f.iterrows():
                render_alert_card(row)

    st.divider()

    # ── FEED DE NOTICIAS ANALIZADAS ──────────────────────────
    section_title("📰 Feed de noticias analizadas por AI")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        h_back = st.selectbox("Período", [24, 48, 72, 168],
                              format_func=lambda x: f"Últimas {x}h",
                              index=1, key="intel_hours")
    with col_f2:
        tipo_filter = st.multiselect("Tipo",
                                     ["riesgo", "oportunidad", "neutro"],
                                     default=["riesgo", "oportunidad"],
                                     key="intel_tipo")
    with col_f3:
        min_relev = st.slider("Relevancia mínima", 0, 100, 30, 5, key="intel_relev")

    df_intel = load_intelligence(hours=h_back)
    if df_intel.empty:
        st.info("Aún no hay noticias analizadas. Corre `python -m intelligence.news_fetcher` "
                "y luego `python -m intelligence.ai_analyst`.")
    else:
        df_intel_f = df_intel[
            df_intel["tipo"].isin(tipo_filter) &
            (df_intel["relevancia_pct"] >= min_relev)
        ]

        st.caption(f"{len(df_intel_f)} noticias relevantes en últimas {h_back}h "
                   f"(de {len(df_intel)} analizadas)")

        # Distribución resumen
        if not df_intel_f.empty:
            tipo_count = df_intel_f["tipo"].value_counts()
            cols_t = st.columns(3)
            for i, t in enumerate(["riesgo", "oportunidad", "neutro"]):
                with cols_t[i]:
                    st.metric(t.capitalize(), int(tipo_count.get(t, 0)))

            for _, row in df_intel_f.head(30).iterrows():
                render_news_card(row)

    st.divider()

    # ── FEED CRUDO (NOTICIAS SIN ANALIZAR) ──────────────────
    with st.expander("📥 Noticias recolectadas (crudas, sin análisis AI)"):
        df_raw = load_recent_news(hours=24, limit=30)
        if df_raw.empty:
            st.info("Sin noticias recolectadas en últimas 24h.")
        else:
            for _, row in df_raw.iterrows():
                tickers = row.get("tickers_mencionados") or []
                if isinstance(tickers, str):
                    tickers = tickers.strip("{}").split(",") if tickers else []
                tk_str = ", ".join(t.strip() for t in tickers if t.strip())
                fecha_str = ""
                try:
                    fecha_str = pd.to_datetime(row["fecha_noticia"]).strftime("%d/%m %H:%M")
                except Exception:
                    pass
                st.markdown(
                    f"- **{row['titulo']}** "
                    f"<span style='color:#8892b0; font-size:0.8rem;'>"
                    f"({row['fuente']} · {fecha_str} · relev preliminar: {row.get('relevancia_preliminar',0)})</span><br>"
                    f"<span style='color:#a0aec0; font-size:0.85rem;'>{(row.get('resumen') or '')[:200]}</span>"
                    + (f"<br>📌 {tk_str}" if tk_str else ""),
                    unsafe_allow_html=True,
                )

    # ── BOTONES DE ACCIÓN ────────────────────────────────────
    st.divider()
    section_title("🛠 Acciones manuales")
    st.caption("Estos comandos también corren automáticamente en GitHub Actions cada 2h.")

    cmd_col1, cmd_col2 = st.columns(2)
    with cmd_col1:
        st.code("python -m intelligence.news_fetcher --hours 6", language="bash")
        st.caption("Trae noticias nuevas de RSS")
    with cmd_col2:
        st.code("python -m intelligence.ai_analyst --limit 20", language="bash")
        st.caption("Analiza pendientes con Claude")

    st.code("python -m intelligence.portfolio_health", language="bash")
    st.caption("Re-evalúa salud de la cartera y genera alertas")

    st.code("python -m intelligence.daily_brief", language="bash")
    st.caption("Genera el Daily Brief consolidado")
