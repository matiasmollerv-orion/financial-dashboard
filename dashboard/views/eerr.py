# ============================================================
# VISTA: ESTADO DE RESULTADOS (P&L)
# ============================================================

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_pct, section_title,
    load_ingresos, load_gastos, load_racional,
)


def render():
    st.title("📋 Estado de Resultados")

    df_ingresos = load_ingresos()
    df_gastos   = load_gastos()
    df_racional = load_racional()

    # ── Preparar ingresos ─────────────────────────────────
    if not df_ingresos.empty:
        df_ingresos = df_ingresos.copy()
        df_ingresos["monto"] = pd.to_numeric(df_ingresos["monto"], errors="coerce")
        df_ingresos["mes"]   = df_ingresos["fecha"].dt.to_period("M").astype(str)
        ingresos_mes = df_ingresos.groupby("mes")["monto"].sum()
    else:
        ingresos_mes = pd.Series(dtype=float)

    # ── Preparar gastos ───────────────────────────────────
    monto_col = "monto_clp" if (not df_gastos.empty and "monto_clp" in df_gastos.columns) else "monto"
    if not df_gastos.empty:
        df_gastos = df_gastos.copy()
        df_gastos[monto_col] = pd.to_numeric(df_gastos[monto_col], errors="coerce")
        df_gastos["mes"]     = df_gastos["fecha"].dt.to_period("M").astype(str)
        gastos_mes = df_gastos.groupby("mes")[monto_col].sum()
    else:
        gastos_mes = pd.Series(dtype=float)

    # ── Preparar inversiones ──────────────────────────────
    if not df_racional.empty:
        df_r = df_racional.copy()
        df_r["monto_clp"] = pd.to_numeric(df_r.get("monto_clp", 0), errors="coerce").fillna(0)
        df_r["mes"]        = df_r["fecha"].dt.to_period("M").astype(str)
        inv_mes = df_r.groupby("mes")["monto_clp"].sum()
    else:
        inv_mes = pd.Series(dtype=float)

    # ── Resumen actual (últimos 12 meses disponibles) ─────
    todos_meses = sorted(set(
        list(ingresos_mes.index) +
        list(gastos_mes.index) +
        list(inv_mes.index)
    ))[-12:]

    st.divider()

    # ── Tabla EERR mensual ────────────────────────────────
    section_title("Resumen mensual")

    rows = []
    for mes in todos_meses:
        ing = ingresos_mes.get(mes, 0)
        gas = gastos_mes.get(mes, 0)
        inv = inv_mes.get(mes, 0)
        ahorro = ing - gas - inv
        tasa_ahorro = (ahorro / ing * 100) if ing else 0
        rows.append({
            "Mes": mes,
            "Ingresos": ing,
            "Gastos": gas,
            "Inversiones": inv,
            "Ahorro Neto": ahorro,
            "Tasa Ahorro": tasa_ahorro,
        })

    if not rows:
        st.info("No hay datos suficientes para mostrar el estado de resultados.")
        return

    df_eerr = pd.DataFrame(rows)

    # KPIs acumulados
    total_ing = df_eerr["Ingresos"].sum()
    total_gas = df_eerr["Gastos"].sum()
    total_inv = df_eerr["Inversiones"].sum()
    total_aho = df_eerr["Ahorro Neto"].sum()
    tasa_prom = (total_aho / total_ing * 100) if total_ing else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Ingresos acum.", fmt_clp(total_ing))
    with c2:
        st.metric("Gastos acum.", fmt_clp(total_gas))
    with c3:
        st.metric("Inversiones acum.", fmt_clp(total_inv))
    with c4:
        st.metric("Ahorro neto", fmt_clp(total_aho))
    with c5:
        st.metric("Tasa ahorro", fmt_pct(tasa_prom))

    st.divider()

    # ── Gráfico cascada mensual ───────────────────────────
    section_title("Flujo mensual: Ingresos vs Gastos vs Inversiones")
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_eerr["Mes"], y=df_eerr["Ingresos"],
        name="Ingresos",
        marker_color="#2ecc71",
    ))
    fig.add_trace(go.Bar(
        x=df_eerr["Mes"], y=-df_eerr["Gastos"],
        name="Gastos",
        marker_color="#e74c3c",
    ))
    fig.add_trace(go.Bar(
        x=df_eerr["Mes"], y=-df_eerr["Inversiones"],
        name="Inversiones",
        marker_color="#4e79a7",
    ))
    fig.add_trace(go.Scatter(
        x=df_eerr["Mes"], y=df_eerr["Ahorro Neto"],
        name="Ahorro Neto",
        mode="lines+markers",
        line=dict(color="#f39c12", width=2),
        marker=dict(size=6),
    ))

    fig.update_layout(
        barmode="relative",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccd6f6",
        margin=dict(t=10, b=10, l=10, r=10),
        height=380,
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#2d3250"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabla detalle ─────────────────────────────────────
    section_title("Detalle mensual")
    tbl = df_eerr.copy()
    for col in ["Ingresos", "Gastos", "Inversiones", "Ahorro Neto"]:
        tbl[col] = tbl[col].apply(fmt_clp)
    tbl["Tasa Ahorro"] = tbl["Tasa Ahorro"].apply(fmt_pct)
    st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ── Desglose gastos si hay datos ──────────────────────
    if not df_gastos.empty and "categoria" in df_gastos.columns:
        st.divider()
        section_title("Distribución de gastos por categoría (acumulado)")
        grp = df_gastos.groupby("categoria")[monto_col].sum().reset_index()
        grp = grp.sort_values(monto_col, ascending=False)

        fig2 = px.bar(
            grp.head(12),
            x=monto_col, y="categoria",
            orientation="h",
            labels={monto_col: "CLP", "categoria": ""},
            color_discrete_sequence=["#4e79a7"],
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccd6f6",
            margin=dict(t=10, b=10, l=10, r=10),
            height=350,
            xaxis=dict(gridcolor="#2d3250"),
            yaxis=dict(showgrid=False, autorange="reversed"),
        )
        st.plotly_chart(fig2, use_container_width=True)
