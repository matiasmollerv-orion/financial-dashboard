# ============================================================
# VISTA: PROYECCIONES PATRIMONIALES
# ============================================================

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, fmt_pct, section_title,
    load_cartera, load_ingresos, load_gastos, get_usd_clp,
)


def render():
    st.title("🔮 Proyecciones Patrimoniales")

    usd_clp     = get_usd_clp()
    df_cartera  = load_cartera()
    df_ingresos = load_ingresos()
    df_gastos   = load_gastos()

    # ── Patrimonio actual ─────────────────────────────────
    total_cl    = 0.0
    total_intl  = 0.0
    total_crypto = 0.0

    if not df_cartera.empty:
        df_cl   = df_cartera[df_cartera["mercado"] == "nacional"].copy()
        df_intl = df_cartera[df_cartera["mercado"] == "internacional"].copy()
        if not df_cl.empty:
            df_cl["valor"] = df_cl["cantidad"] * df_cl["precio_actual"]
            total_cl = df_cl["valor"].sum()
        if not df_intl.empty:
            df_intl["valor_usd"] = df_intl["cantidad"] * df_intl["precio_actual"]
            total_intl = df_intl["valor_usd"].sum() * usd_clp

    patrimonio_actual = total_cl + total_intl + total_crypto

    # ── Parámetros ajustables ─────────────────────────────
    st.markdown("### ⚙️ Parámetros de proyección")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sueldo_mensual = st.number_input(
            "Sueldo neto mensual (CLP)",
            min_value=0, max_value=50_000_000,
            value=4_862_792, step=100_000,
            format="%d"
        )
    with col2:
        gastos_mensuales = st.number_input(
            "Gastos mensuales estimados (CLP)",
            min_value=0, max_value=20_000_000,
            value=1_500_000, step=50_000,
            format="%d"
        )
    with col3:
        retorno_anual = st.slider(
            "Retorno anual del portafolio (%)",
            min_value=0.0, max_value=30.0,
            value=8.0, step=0.5
        )
    with col4:
        horizonte = st.slider(
            "Horizonte (años)",
            min_value=1, max_value=40,
            value=20, step=1
        )

    col5, col6 = st.columns(2)
    with col5:
        aumento_sueldo = st.slider(
            "Aumento sueldo anual (%)",
            min_value=0.0, max_value=20.0,
            value=3.0, step=0.5
        )
    with col6:
        inflacion = st.slider(
            "Inflación anual (%)",
            min_value=0.0, max_value=20.0,
            value=4.0, step=0.5
        )

    ahorro_mensual = sueldo_mensual - gastos_mensuales
    tasa_ahorro = (ahorro_mensual / sueldo_mensual * 100) if sueldo_mensual else 0

    st.info(f"💡 Ahorro mensual estimado: **{fmt_clp(ahorro_mensual)}** | Tasa de ahorro: **{fmt_pct(tasa_ahorro)}**")

    if patrimonio_actual == 0:
        st.warning("No hay patrimonio inicial cargado. Verifica que la cartera esté en Supabase.")

    st.divider()

    # ── Proyección ────────────────────────────────────────
    r_mensual     = retorno_anual / 100 / 12
    infl_mensual  = inflacion / 100 / 12
    aum_mensual   = aumento_sueldo / 100 / 12

    meses = horizonte * 12
    patrimonio = patrimonio_actual
    sueldo     = sueldo_mensual
    gastos_m   = gastos_mensuales

    historial_pat  = [patrimonio_actual]
    historial_inv  = [0.0]
    historial_mes  = [0]

    for m in range(1, meses + 1):
        # Crecer patrimonio por retorno
        patrimonio *= (1 + r_mensual)
        # Sumar ahorro del mes
        ahorro_m = sueldo - gastos_m
        if ahorro_m > 0:
            patrimonio += ahorro_m
        # Actualizar sueldo y gastos
        sueldo   *= (1 + aum_mensual)
        gastos_m *= (1 + infl_mensual)

        if m % 12 == 0:
            historial_pat.append(patrimonio)
            historial_inv.append(historial_pat[-1] - historial_pat[-2] if len(historial_pat) > 1 else 0)
            historial_mes.append(m // 12)

    # Escenarios: conservador (-3%), base, optimista (+3%)
    def proyectar(retorno_base_anual):
        r = retorno_base_anual / 100 / 12
        p = patrimonio_actual
        s = sueldo_mensual
        g = gastos_mensuales
        hist = [p]
        for m in range(1, meses + 1):
            p *= (1 + r)
            ahorro = s - g
            if ahorro > 0:
                p += ahorro
            s *= (1 + aum_mensual)
            g *= (1 + infl_mensual)
            if m % 12 == 0:
                hist.append(p)
        return hist

    años_label = list(range(0, horizonte + 1))
    pat_cons   = proyectar(max(0, retorno_anual - 3))
    pat_base   = proyectar(retorno_anual)
    pat_opt    = proyectar(retorno_anual + 3)

    # ── Gráfico de proyección ─────────────────────────────
    section_title(f"Proyección a {horizonte} años")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=años_label, y=pat_opt,
        name=f"Optimista ({retorno_anual+3:.1f}%)",
        mode="lines",
        line=dict(color="#2ecc71", width=1, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(46,204,113,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=años_label, y=pat_base,
        name=f"Base ({retorno_anual:.1f}%)",
        mode="lines+markers",
        line=dict(color="#4e79a7", width=2),
        marker=dict(size=5),
    ))
    fig.add_trace(go.Scatter(
        x=años_label, y=pat_cons,
        name=f"Conservador ({max(0,retorno_anual-3):.1f}%)",
        mode="lines",
        line=dict(color="#e74c3c", width=1, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(231,76,60,0.08)",
    ))

    # Marcar hitos
    meta_100m = 100_000_000
    meta_500m = 500_000_000
    for meta, label in [(meta_100m, "Meta $100M"), (meta_500m, "Meta $500M")]:
        if pat_opt[-1] >= meta:
            fig.add_hline(
                y=meta,
                line_dash="dash",
                line_color="#f39c12",
                annotation_text=label,
                annotation_position="right",
            )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccd6f6",
        margin=dict(t=20, b=20, l=10, r=80),
        height=400,
        xaxis=dict(
            title="Años",
            showgrid=False,
            tickmode="linear",
            dtick=max(1, horizonte // 10),
        ),
        yaxis=dict(
            title="Patrimonio (CLP)",
            gridcolor="#2d3250",
            tickformat=",.0f",
        ),
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabla de hitos ────────────────────────────────────
    section_title("Patrimonio proyectado por año (escenario base)")

    hitos = []
    for i, (año, val) in enumerate(zip(años_label, pat_base)):
        if i == 0 or año % max(1, horizonte // 10) == 0 or año == horizonte:
            hitos.append({
                "Año": año,
                "Patrimonio": fmt_clp(val),
                "vs. Hoy": fmt_pct((val / patrimonio_actual - 1) * 100) if patrimonio_actual else "-",
            })

    st.dataframe(pd.DataFrame(hitos), hide_index=True, use_container_width=True)

    st.divider()

    # ── Libertad financiera ───────────────────────────────
    section_title("🎯 Calculadora de Libertad Financiera")

    col_lf1, col_lf2 = st.columns(2)
    with col_lf1:
        gasto_retiro = st.number_input(
            "Gasto mensual en retiro (CLP)",
            min_value=100_000, max_value=20_000_000,
            value=3_000_000, step=100_000,
            format="%d"
        )
    with col_lf2:
        tasa_retiro = st.slider(
            "Tasa de retiro anual (regla 4% = recomendada)",
            min_value=2.0, max_value=8.0,
            value=4.0, step=0.5
        )

    gasto_anual_retiro = gasto_retiro * 12
    patrimonio_fi = gasto_anual_retiro / (tasa_retiro / 100)

    # ¿Cuándo llega?
    año_fi = None
    for i, val in enumerate(pat_base):
        if val >= patrimonio_fi:
            año_fi = años_label[i]
            break

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.metric(
            "Patrimonio necesario (FI)",
            fmt_clp(patrimonio_fi),
            help=f"Basado en regla del {tasa_retiro}%"
        )
    with col_r2:
        if año_fi is not None:
            from datetime import date
            año_llegada = date.today().year + año_fi
            st.metric(
                "Año estimado de FI",
                str(año_llegada),
                delta=f"en {año_fi} años"
            )
        else:
            st.metric(
                "Libertad financiera",
                f"> {horizonte} años",
                delta="Aumenta retorno o ahorro",
                delta_color="inverse"
            )
