# ============================================================
# VISTA: RESUMEN PATRIMONIAL
# ============================================================

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, fmt_pct,
    fmt_clp_safe, fmt_usd_safe, metric_safe, amounts_hidden,
    section_title, ASSET_COLORS,
    load_cartera, load_buda, load_ingresos, get_usd_clp,
)
from dashboard.mappings import get_tipo, get_pais


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega tipo, pais y valor_clp a cartera."""
    df = df.copy()
    df["tipo"] = df.apply(lambda r: get_tipo(r["ticker"], r.get("mercado", "")), axis=1)
    df["pais"] = df.apply(lambda r: get_pais(r["ticker"], r.get("mercado", "")), axis=1)
    usd_clp = get_usd_clp()
    df["precio_actual"] = pd.to_numeric(df["precio_actual"], errors="coerce")
    df["precio_compra"]  = pd.to_numeric(df["precio_compra"],  errors="coerce")
    df["cantidad"]       = pd.to_numeric(df["cantidad"],       errors="coerce")
    df["valor_usd"]  = df["cantidad"] * df["precio_actual"]
    df["costo_usd"]  = df["cantidad"] * df["precio_compra"]
    if "moneda" not in df.columns:
        df["moneda"] = "USD"
    df["valor_clp"] = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * usd_clp,
        axis=1
    )
    df["costo_clp"] = df.apply(
        lambda r: r["costo_usd"] if r.get("moneda") == "CLP" else r["costo_usd"] * usd_clp,
        axis=1
    )
    df["ganancia_clp"] = df["valor_clp"] - df["costo_clp"]
    costo_safe = df["costo_clp"].where(df["costo_clp"] != 0, other=np.nan)
    df["retorno_pct"]  = (df["ganancia_clp"] / costo_safe * 100).round(2)
    return df


def render():
    st.title("📊 Resumen Patrimonial")

    usd_clp = get_usd_clp()
    df_raw = load_cartera()
    df_ingresos = load_ingresos()

    if df_raw.empty:
        st.warning("No hay datos de cartera. Ejecuta load_portfolio.py primero.")
        return

    df = _enrich(df_raw)

    # ── Filtros globales ──────────────────────────────────
    with st.expander("🔍 Filtros", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            tipos_disp = sorted(df["tipo"].dropna().unique().tolist())
            tipos_sel  = st.multiselect("Tipo de activo", tipos_disp, default=tipos_disp, key="res_tipos")
        with col_f2:
            paises_disp = sorted(df["pais"].dropna().unique().tolist())
            paises_sel  = st.multiselect("País / Mercado", paises_disp, default=paises_disp, key="res_paises")

    # Aplicar filtros
    df_f = df.copy()
    if tipos_sel:
        df_f = df_f[df_f["tipo"].isin(tipos_sel)]
    if paises_sel:
        df_f = df_f[df_f["pais"].isin(paises_sel)]

    # ── KPIs ──────────────────────────────────────────────
    total_clp  = df_f["valor_clp"].sum()
    costo_clp  = df_f["costo_clp"].sum()
    ganancia   = df_f["ganancia_clp"].sum()
    retorno    = (ganancia / costo_clp * 100) if costo_clp else 0
    n_pos      = len(df_f)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_safe("💼 Patrimonio (filtrado)", fmt_clp(total_clp))
    with c2:
        metric_safe("📥 Costo total invertido", fmt_clp(costo_clp))
    with c3:
        metric_safe("📈 Ganancia / Pérdida", fmt_clp(ganancia), delta=fmt_pct(retorno))
    with c4:
        st.metric("🗂 Posiciones", str(n_pos))

    st.divider()

    # ── Gráficos: fila 1 ──────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        section_title("Por tipo de activo")
        grp_tipo = df_f.groupby("tipo")["valor_clp"].sum().reset_index().sort_values("valor_clp", ascending=False)
        fig = go.Figure(go.Pie(
            labels=grp_tipo["tipo"],
            values=grp_tipo["valor_clp"],
            hole=0.52,
            textinfo="label+percent",
            textfont_size=12,
            marker=dict(colors=ASSET_COLORS),
        ))
        fig.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=10, r=10),
            height=300,
            annotations=[dict(
                text=f"<b>{fmt_clp_safe(total_clp)}</b>",
                x=0.5, y=0.5, font_size=13, showarrow=False, font_color="#ccd6f6"
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section_title("Por país / mercado")
        grp_pais = df_f.groupby("pais")["valor_clp"].sum().reset_index().sort_values("valor_clp", ascending=False)
        fig2 = go.Figure(go.Pie(
            labels=grp_pais["pais"],
            values=grp_pais["valor_clp"],
            hole=0.52,
            textinfo="label+percent",
            textfont_size=12,
            marker=dict(colors=ASSET_COLORS[5:]),
        ))
        fig2.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=10, r=10),
            height=300,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Gráficos: fila 2 ──────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        section_title("Distribución por tipo (barras)")
        fig3 = px.bar(
            grp_tipo,
            x="valor_clp", y="tipo",
            orientation="h",
            color_discrete_sequence=["#4e79a7"],
            labels={"valor_clp": "CLP", "tipo": ""},
        )
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccd6f6",
            margin=dict(t=5, b=5, l=5, r=5),
            height=250,
            xaxis=dict(tickformat=",.0f", gridcolor="#2d3250"),
            yaxis=dict(showgrid=False, autorange="reversed"),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        section_title("Top 10 posiciones")
        top10 = df_f.nlargest(10, "valor_clp")[["ticker", "valor_clp", "retorno_pct"]].copy()
        fig4 = px.bar(
            top10.sort_values("valor_clp"),
            x="valor_clp", y="ticker",
            orientation="h",
            color="retorno_pct",
            color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
            color_continuous_midpoint=0,
            labels={"valor_clp": "CLP", "ticker": "", "retorno_pct": "Retorno %"},
        )
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccd6f6",
            margin=dict(t=5, b=5, l=5, r=5),
            height=250,
            xaxis=dict(tickformat=",.0f", gridcolor="#2d3250"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    # ── Tabla resumen por tipo ────────────────────────────
    section_title("Resumen por tipo de activo")
    grp_full = df_f.groupby("tipo").agg(
        Posiciones=("ticker", "count"),
        Valor_CLP=("valor_clp", "sum"),
        Costo_CLP=("costo_clp", "sum"),
        Ganancia_CLP=("ganancia_clp", "sum"),
    ).reset_index().sort_values("Valor_CLP", ascending=False)
    costo_safe2 = grp_full["Costo_CLP"].where(grp_full["Costo_CLP"] != 0, other=np.nan)
    grp_full["Retorno %"] = (grp_full["Ganancia_CLP"] / costo_safe2 * 100).round(1)
    grp_full["Valor_CLP"]    = grp_full["Valor_CLP"].apply(fmt_clp_safe)
    grp_full["Costo_CLP"]    = grp_full["Costo_CLP"].apply(fmt_clp_safe)
    grp_full["Ganancia_CLP"] = grp_full["Ganancia_CLP"].apply(fmt_clp_safe)
    grp_full["Retorno %"]    = grp_full["Retorno %"].apply(fmt_pct)
    grp_full.columns = ["Tipo", "Posiciones", "Valor CLP", "Costo CLP", "Ganancia CLP", "Retorno %"]
    st.dataframe(grp_full, hide_index=True, use_container_width=True)

    # ── Ingresos ──────────────────────────────────────────
    if not df_ingresos.empty:
        st.divider()
        section_title("💰 Ingresos registrados")
        total_ing = pd.to_numeric(df_ingresos["monto"], errors="coerce").sum()
        avg       = total_ing / len(df_ingresos)
        c1, c2, c3 = st.columns(3)
        with c1: metric_safe("Total 12 meses", fmt_clp(total_ing))
        with c2: metric_safe("Promedio mensual", fmt_clp(avg))
        with c3: st.metric("Tasa inversión / ingreso", fmt_pct(costo_clp / total_ing * 100) if total_ing else "-")
