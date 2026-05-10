# ============================================================
# VISTA: RESUMEN / HOME
# ============================================================

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, fmt_pct,
    section_title, ASSET_COLORS,
    load_cartera, load_buda, load_ingresos, get_usd_clp,
)


def render():
    st.title("📊 Resumen Patrimonial")

    usd_clp = get_usd_clp()

    # ── Cargar datos ──────────────────────────────────────
    df_cartera = load_cartera()
    df_buda    = load_buda()
    df_ingresos = load_ingresos()

    # ── Calcular patrimonio ───────────────────────────────
    total_cl   = 0.0
    total_intl = 0.0
    total_crypto = 0.0

    if not df_cartera.empty:
        df_cl   = df_cartera[df_cartera["mercado"] == "nacional"]
        df_intl = df_cartera[df_cartera["mercado"] == "internacional"]

        if not df_cl.empty:
            df_cl = df_cl.copy()
            df_cl["valor_actual"] = df_cl["cantidad"] * df_cl["precio_actual"]
            total_cl = df_cl["valor_actual"].sum()

        if not df_intl.empty:
            df_intl = df_intl.copy()
            df_intl["valor_actual_usd"] = df_intl["cantidad"] * df_intl["precio_actual"]
            total_intl = df_intl["valor_actual_usd"].sum() * usd_clp

    # Crypto (Buda): usa cantidad y precio_usd → CLP
    if not df_buda.empty:
        # Aproximación: suma de montos en CLP invertidos (costo base)
        if "monto_clp" in df_buda.columns:
            total_crypto = pd.to_numeric(df_buda["monto_clp"], errors="coerce").sum()

    total_patrimonio = total_cl + total_intl + total_crypto

    # ── KPIs principales ──────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💼 Patrimonio Total", fmt_clp(total_patrimonio))
    with col2:
        st.metric("🇨🇱 Acciones Chile", fmt_clp(total_cl))
    with col3:
        usd_val = total_intl / usd_clp if usd_clp else 0
        st.metric("🌎 Stocks Internacionales", fmt_usd(usd_val, 0),
                  help=f"Equivalente: {fmt_clp(total_intl)}")
    with col4:
        st.metric("₿ Crypto (costo base)", fmt_clp(total_crypto))

    st.divider()

    # ── Composición del portafolio ────────────────────────
    col_left, col_right = st.columns([1, 1])

    with col_left:
        section_title("Composición del Patrimonio")

        labels = []
        values = []
        if total_cl > 0:
            labels.append("Acciones Chile")
            values.append(total_cl)
        if total_intl > 0:
            labels.append("Stocks Internacionales")
            values.append(total_intl)
        if total_crypto > 0:
            labels.append("Crypto")
            values.append(total_crypto)

        if values:
            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                textinfo="label+percent",
                textfont_size=13,
                marker=dict(colors=["#4e79a7", "#f28e2b", "#f7c948"]),
            ))
            fig.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=280,
                annotations=[dict(
                    text=f"<b>{fmt_clp(total_patrimonio)}</b>",
                    x=0.5, y=0.5, font_size=14,
                    showarrow=False, font_color="#ccd6f6"
                )],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de cartera.")

    with col_right:
        section_title("Distribución por Mercado")

        if not df_cartera.empty:
            df_intl_plot = df_cartera[df_cartera["mercado"] == "internacional"].copy()
            if not df_intl_plot.empty:
                df_intl_plot["valor_usd"] = df_intl_plot["cantidad"] * df_intl_plot["precio_actual"]
                # Top 10 + Otros
                top10 = df_intl_plot.nlargest(10, "valor_usd")[["ticker", "valor_usd"]]
                otros = df_intl_plot[~df_intl_plot["ticker"].isin(top10["ticker"])]["valor_usd"].sum()
                if otros > 0:
                    top10 = pd.concat([
                        top10,
                        pd.DataFrame([{"ticker": "Otros", "valor_usd": otros}])
                    ], ignore_index=True)

                fig2 = px.bar(
                    top10.sort_values("valor_usd"),
                    x="valor_usd", y="ticker",
                    orientation="h",
                    color_discrete_sequence=["#4e79a7"],
                    labels={"valor_usd": "USD", "ticker": ""},
                )
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#ccd6f6",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=280,
                    xaxis=dict(
                        tickformat=",.0f",
                        showgrid=True,
                        gridcolor="#2d3250",
                    ),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin datos de portafolio internacional.")

    st.divider()

    # ── Top posiciones ────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_title("🇨🇱 Top Acciones Chilenas")
        if not df_cartera.empty:
            df_cl2 = df_cartera[df_cartera["mercado"] == "nacional"].copy()
            if not df_cl2.empty:
                df_cl2["valor_actual"] = df_cl2["cantidad"] * df_cl2["precio_actual"]
                df_cl2["costo_total"]  = df_cl2["cantidad"] * df_cl2["precio_compra"]
                df_cl2["ganancia"]     = df_cl2["valor_actual"] - df_cl2["costo_total"]
                df_cl2["retorno_pct"]  = (df_cl2["ganancia"] / df_cl2["costo_total"] * 100).round(1)

                show = df_cl2[["ticker", "empresa", "valor_actual", "ganancia", "retorno_pct"]].copy()
                show = show.sort_values("valor_actual", ascending=False)
                show.columns = ["Ticker", "Empresa", "Valor Actual", "Ganancia", "Retorno %"]
                show["Valor Actual"] = show["Valor Actual"].apply(fmt_clp)
                show["Ganancia"]     = show["Ganancia"].apply(fmt_clp)
                show["Retorno %"]    = show["Retorno %"].apply(lambda x: fmt_pct(x))
                st.dataframe(show, hide_index=True, use_container_width=True)
            else:
                st.info("Sin datos.")
        else:
            st.info("Sin datos.")

    with col_b:
        section_title("🌎 Top Stocks Internacionales")
        if not df_cartera.empty:
            df_i2 = df_cartera[df_cartera["mercado"] == "internacional"].copy()
            if not df_i2.empty:
                df_i2["valor_usd"]    = df_i2["cantidad"] * df_i2["precio_actual"]
                df_i2["costo_usd"]    = df_i2["cantidad"] * df_i2["precio_compra"]
                df_i2["ganancia_usd"] = df_i2["valor_usd"] - df_i2["costo_usd"]
                df_i2["retorno_pct"]  = (df_i2["ganancia_usd"] / df_i2["costo_usd"] * 100).round(1)

                show_i = df_i2[["ticker", "empresa", "valor_usd", "ganancia_usd", "retorno_pct"]].copy()
                show_i = show_i.sort_values("valor_usd", ascending=False).head(15)
                show_i.columns = ["Ticker", "Empresa", "Valor USD", "Ganancia USD", "Retorno %"]
                show_i["Valor USD"]    = show_i["Valor USD"].apply(lambda x: fmt_usd(x, 0))
                show_i["Ganancia USD"] = show_i["Ganancia USD"].apply(lambda x: fmt_usd(x, 0))
                show_i["Retorno %"]    = show_i["Retorno %"].apply(lambda x: fmt_pct(x))
                st.dataframe(show_i, hide_index=True, use_container_width=True)
            else:
                st.info("Sin datos.")
        else:
            st.info("Sin datos.")

    st.divider()

    # ── Ingresos acumulados ───────────────────────────────
    if not df_ingresos.empty:
        section_title("💰 Ingresos Registrados")
        total_ingresos = pd.to_numeric(df_ingresos["monto"], errors="coerce").sum()
        avg_mensual = total_ingresos / len(df_ingresos) if len(df_ingresos) > 0 else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total ingresos registrados", fmt_clp(total_ingresos))
        with c2:
            st.metric("Promedio mensual", fmt_clp(avg_mensual))
        with c3:
            st.metric("Meses registrados", str(len(df_ingresos)))
