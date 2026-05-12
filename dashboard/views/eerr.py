# ============================================================
# VISTA: ESTADO DE RESULTADOS MENSUAL
# ============================================================

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_pct, section_title,
    load_ingresos, load_gastos, load_racional,
)
from dashboard.categorias import categorizar_df


def render():
    st.title("📋 Estado de Resultados")

    df_ingresos  = load_ingresos()
    df_gastos    = load_gastos()
    df_racional  = load_racional()

    # Excluir pagos de tarjeta e inversiones (para no duplicar gastos reales)
    EXCLUIR_TOP  = ["Investments"]
    EXCLUIR_SUBS = ["Pago TC"]
    if not df_gastos.empty:
        df_gastos = categorizar_df(df_gastos.copy())
        df_gastos["monto"] = pd.to_numeric(df_gastos["monto"], errors="coerce")
        df_gastos = df_gastos[
            ~df_gastos["top_level"].isin(EXCLUIR_TOP) &
            ~df_gastos["subcategoria"].isin(EXCLUIR_SUBS)
        ]

    # ── Preparar datos mensuales ──────────────────────────
    def to_mensual(df, col):
        if df.empty or col not in df.columns:
            return pd.Series(dtype=float)
        df = df.copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df["mes"] = df["fecha"].dt.to_period("M").astype(str)
        return df.groupby("mes")[col].sum()

    ing_mes  = to_mensual(df_ingresos, "monto")
    gas_mes  = to_mensual(df_gastos, "monto_clp" if (not df_gastos.empty and "monto_clp" in df_gastos.columns) else "monto")
    inv_mes  = to_mensual(df_racional, "monto_clp") if not df_racional.empty else pd.Series(dtype=float)

    # Unir todos los meses disponibles
    todos = sorted(set(list(ing_mes.index) + list(gas_mes.index) + list(inv_mes.index)))
    if not todos:
        st.info("Sin datos suficientes para el EERR. Registra ingresos y gastos primero.")
        return

    # ── Filtro de período ─────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        años_disp = sorted(set(m[:4] for m in todos), reverse=True)
        año_sel   = st.selectbox("Año", ["Todos"] + años_disp)
    with col_f2:
        n_meses = st.slider("Últimos N meses", 1, len(todos), min(12, len(todos)))

    if año_sel != "Todos":
        todos_f = [m for m in todos if m.startswith(año_sel)]
    else:
        todos_f = todos[-n_meses:]

    # ── Construir tabla EERR ──────────────────────────────
    rows = []
    for mes in todos_f:
        ing  = ing_mes.get(mes, 0)
        gas  = gas_mes.get(mes, 0)
        inv  = inv_mes.get(mes, 0)

        margen_bruto     = ing - gas
        resultado_op     = margen_bruto - inv
        tasa_ahorro      = (resultado_op / ing * 100) if ing else 0
        tasa_gasto       = (gas / ing * 100) if ing else 0
        tasa_inversion   = (inv / ing * 100) if ing else 0

        rows.append({
            "Mes": mes,
            "Ingresos": ing,
            "Gastos": gas,
            "Margen Bruto": margen_bruto,
            "Inversiones": inv,
            "Resultado Operacional": resultado_op,
            "Tasa Gasto %": tasa_gasto,
            "Tasa Inversión %": tasa_inversion,
            "Tasa Ahorro %": tasa_ahorro,
        })

    df_eerr = pd.DataFrame(rows)
    if df_eerr.empty:
        st.warning("Sin datos para el período seleccionado.")
        return

    # ── KPIs acumulados ───────────────────────────────────
    total_ing  = df_eerr["Ingresos"].sum()
    total_gas  = df_eerr["Gastos"].sum()
    total_inv  = df_eerr["Inversiones"].sum()
    total_res  = df_eerr["Resultado Operacional"].sum()
    tasa_aho   = (total_res / total_ing * 100) if total_ing else 0
    tasa_gas   = (total_gas / total_ing * 100) if total_ing else 0
    tasa_inv   = (total_inv / total_ing * 100) if total_ing else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Ingresos", fmt_clp(total_ing))
    with c2: st.metric("Gastos", fmt_clp(total_gas), delta=f"{tasa_gas:.1f}% ing.", delta_color="inverse")
    with c3: st.metric("Inversiones", fmt_clp(total_inv), delta=f"{tasa_inv:.1f}% ing.")
    with c4: st.metric("Resultado", fmt_clp(total_res))
    with c5: st.metric("Tasa ahorro", fmt_pct(tasa_aho))

    st.divider()

    # ── Gráfico de cascada mensual ────────────────────────
    section_title("Flujo mensual")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_eerr["Mes"], y=df_eerr["Ingresos"],    name="Ingresos",     marker_color="#2ecc71"))
    fig.add_trace(go.Bar(x=df_eerr["Mes"], y=-df_eerr["Gastos"],     name="Gastos",       marker_color="#e74c3c"))
    fig.add_trace(go.Bar(x=df_eerr["Mes"], y=-df_eerr["Inversiones"],name="Inversiones",  marker_color="#4e79a7"))
    fig.add_trace(go.Scatter(
        x=df_eerr["Mes"], y=df_eerr["Resultado Operacional"],
        name="Resultado", mode="lines+markers",
        line=dict(color="#f39c12", width=2), marker=dict(size=7),
    ))
    fig.update_layout(
        barmode="relative",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccd6f6",
        margin=dict(t=10, b=10, l=10, r=10), height=380,
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#2d3250"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Gráfico de tasas ──────────────────────────────────
    section_title("Distribución del ingreso por mes (%)")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df_eerr["Mes"], y=df_eerr["Tasa Gasto %"],      name="% Gasto",      marker_color="#e74c3c", opacity=0.8))
    fig2.add_trace(go.Bar(x=df_eerr["Mes"], y=df_eerr["Tasa Inversión %"], name="% Inversión",   marker_color="#4e79a7", opacity=0.8))
    fig2.add_trace(go.Bar(x=df_eerr["Mes"], y=df_eerr["Tasa Ahorro %"],    name="% Ahorro neto", marker_color="#2ecc71", opacity=0.8))
    fig2.add_hline(y=0, line_color="#888", line_width=1)
    fig2.update_layout(
        barmode="relative",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccd6f6",
        margin=dict(t=10, b=10, l=10, r=10), height=280,
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#2d3250", ticksuffix="%"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Tabla EERR detallada (transpuesta: filas = líneas, columnas = meses) ──
    section_title("Estado de Resultados mensual detallado")

    tbl_num = df_eerr.copy()
    # Formatear columnas de monto
    lineas_clp = ["Ingresos", "Gastos", "Margen Bruto", "Inversiones", "Resultado Operacional"]
    lineas_pct = ["Tasa Gasto %", "Tasa Inversión %", "Tasa Ahorro %"]
    tbl_fmt = tbl_num.copy()
    for col in lineas_clp:
        tbl_fmt[col] = tbl_fmt[col].apply(fmt_clp)
    for col in lineas_pct:
        tbl_fmt[col] = tbl_fmt[col].apply(fmt_pct)

    # Transponer: Mes como columna de índice → columnas del DF
    tbl_T = tbl_fmt.set_index("Mes")[lineas_clp + lineas_pct].T
    tbl_T.index.name = "Línea"
    tbl_T = tbl_T.reset_index()
    st.dataframe(tbl_T, hide_index=True, use_container_width=True)

    # ── Desglose categorías de gasto ─────────────────────
    if not df_gastos.empty:
        st.divider()
        section_title("Desglose de gastos por categoría")
        monto_col = "monto_clp" if "monto_clp" in df_gastos.columns else "monto"
        # df_gastos ya tiene categorías y está filtrado (sin Pago TC ni Investments)
        df_g = df_gastos.copy()
        df_g[monto_col] = pd.to_numeric(df_g[monto_col], errors="coerce")
        df_g["mes"] = df_g["fecha"].dt.to_period("M").astype(str)
        df_g = df_g[df_g["mes"].isin(todos_f)]
        grp = (df_g.groupby(["top_level", "subcategoria"])[monto_col]
               .sum().reset_index().sort_values(monto_col, ascending=False))
        total_eerr = grp[monto_col].sum()
        grp["% Total"] = (grp[monto_col] / total_eerr * 100).round(1).astype(str) + "%"
        grp[monto_col] = grp[monto_col].apply(fmt_clp)
        grp.columns = ["Nivel", "Subcategoría", "Total", "% Total"]
        st.dataframe(grp, hide_index=True, use_container_width=True)
