# ============================================================
# VISTA: INVERSIONES
# ============================================================

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, fmt_pct,
    section_title, ASSET_COLORS,
    load_cartera, load_racional, load_buda, get_usd_clp,
)
from dashboard.mappings import get_tipo, get_pais

USD_CLP = get_usd_clp()


def _enrich(df):
    df = df.copy()
    df["tipo"] = df.apply(lambda r: get_tipo(r["ticker"], r.get("mercado", "")), axis=1)
    df["pais"] = df.apply(lambda r: get_pais(r["ticker"], r.get("mercado", "")), axis=1)
    for col in ["precio_actual", "precio_compra", "cantidad"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["valor_usd"]     = df["cantidad"] * df["precio_actual"]
    df["costo_usd"]     = df["cantidad"] * df["precio_compra"]
    if "moneda" not in df.columns:
        df["moneda"] = "USD"
    df["valor_clp"]     = df.apply(lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP, axis=1)
    df["costo_clp"]     = df.apply(lambda r: r["costo_usd"] if r.get("moneda") == "CLP" else r["costo_usd"] * USD_CLP, axis=1)
    df["ganancia_clp"]  = df["valor_clp"] - df["costo_clp"]
    costo_safe = df["costo_clp"].where(df["costo_clp"] != 0, other=np.nan)
    df["retorno_pct"]   = (df["ganancia_clp"] / costo_safe * 100).round(2)
    return df


def render():
    st.title("📈 Inversiones")

    df_cartera  = load_cartera()
    df_racional = load_racional()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Consolidado",
        "🇨🇱 Acciones Chile",
        "🌎 Internacional",
        "📊 Historial Racional",
    ])

    # ────────────────────────────────────────────────────────
    # TAB 1: CONSOLIDADO
    # ────────────────────────────────────────────────────────
    with tab1:
        if df_cartera.empty:
            st.info("Sin datos.")
        else:
            df = _enrich(df_cartera)

            # KPIs totales
            total_val  = df["valor_clp"].sum()
            total_cost = df["costo_clp"].sum()
            total_gan  = df["ganancia_clp"].sum()
            total_ret  = (total_gan / total_cost * 100) if total_cost else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Valor total", fmt_clp(total_val))
            with c2: st.metric("Total invertido", fmt_clp(total_cost))
            with c3: st.metric("Ganancia / Pérdida", fmt_clp(total_gan), delta=fmt_pct(total_ret))
            with c4: st.metric("Posiciones", str(len(df)))

            st.divider()

            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                tipos = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist())
                tipo_sel = st.selectbox("Tipo", tipos, key="con_tipo")
            with col_f2:
                paises = ["Todos"] + sorted(df["pais"].dropna().unique().tolist())
                pais_sel = st.selectbox("País", paises, key="con_pais")
            with col_f3:
                orden = st.selectbox("Ordenar por", ["Valor ↓", "Ganancia ↓", "Retorno % ↓", "Ticker A→Z"], key="con_orden")

            df_f = df.copy()
            if tipo_sel != "Todos":
                df_f = df_f[df_f["tipo"] == tipo_sel]
            if pais_sel != "Todos":
                df_f = df_f[df_f["pais"] == pais_sel]

            sort_map = {
                "Valor ↓": ("valor_clp", False),
                "Ganancia ↓": ("ganancia_clp", False),
                "Retorno % ↓": ("retorno_pct", False),
                "Ticker A→Z": ("ticker", True),
            }
            sc, sa = sort_map[orden]
            df_f = df_f.sort_values(sc, ascending=sa)

            # Treemap
            section_title(f"Mapa de posiciones ({len(df_f)} activos)")
            fig = px.treemap(
                df_f,
                path=["tipo", "ticker"],
                values="valor_clp",
                color="retorno_pct",
                color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                color_continuous_midpoint=0,
                custom_data=["empresa", "ganancia_clp"],
            )
            fig.update_traces(
                texttemplate="<b>%{label}</b><br>%{value:,.0f}",
                hovertemplate="<b>%{label}</b><br>%{customdata[0]}<br>Valor: %{value:,.0f}<br>Ganancia: %{customdata[1]:,.0f}<extra></extra>",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Gráfico de inversión por período ─────────────
            st.divider()
            section_title("Inversión acumulada por período (Historial Racional)")

            if not df_racional.empty and "monto_clp" in df_racional.columns:
                df_r = df_racional.copy()
                df_r["fecha"]    = pd.to_datetime(df_r["fecha"])
                df_r["monto_clp"] = pd.to_numeric(df_r["monto_clp"], errors="coerce")

                periodo = st.radio(
                    "Agrupar por",
                    ["Semana", "Mes", "Quarter", "Año"],
                    horizontal=True,
                    key="con_periodo"
                )

                freq_map = {"Semana": "W", "Mes": "ME", "Quarter": "QE", "Año": "YE"}
                label_map = {"Semana": "%Y-W%V", "Mes": "%Y-%m", "Quarter": None, "Año": "%Y"}

                freq = freq_map[periodo]
                df_r["periodo"] = df_r["fecha"].dt.to_period(
                    {"W":"W","ME":"M","QE":"Q","YE":"Y"}[freq]
                ).astype(str)

                grp = df_r.groupby(["periodo", "mercado"])["monto_clp"].sum().reset_index()

                fig2 = px.bar(
                    grp,
                    x="periodo", y="monto_clp",
                    color="mercado",
                    barmode="stack",
                    labels={"periodo": "", "monto_clp": "CLP", "mercado": "Mercado"},
                    color_discrete_map={"nacional": "#4e79a7", "internacional": "#f28e2b"},
                )
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#ccd6f6",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=320,
                    xaxis=dict(showgrid=False, tickangle=-45),
                    yaxis=dict(gridcolor="#2d3250"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sin historial de transacciones.")

            # Tabla
            section_title("Detalle completo")
            tbl = df_f[["ticker","empresa","tipo","pais","mercado","cantidad","valor_clp","costo_clp","ganancia_clp","retorno_pct"]].copy()
            tbl["valor_clp"]    = tbl["valor_clp"].apply(fmt_clp)
            tbl["costo_clp"]    = tbl["costo_clp"].apply(fmt_clp)
            tbl["ganancia_clp"] = tbl["ganancia_clp"].apply(fmt_clp)
            tbl["retorno_pct"]  = tbl["retorno_pct"].apply(fmt_pct)
            tbl.columns = ["Ticker","Empresa","Tipo","País","Mercado","Cantidad","Valor CLP","Costo CLP","Ganancia CLP","Retorno %"]
            st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 2: ACCIONES CHILENAS
    # ────────────────────────────────────────────────────────
    with tab2:
        if df_cartera.empty:
            st.info("Sin datos.")
        else:
            df = _enrich(df_cartera)
            df_cl = df[df["mercado"] == "nacional"].sort_values("valor_clp", ascending=False)
            if df_cl.empty:
                st.info("Sin posiciones chilenas.")
            else:
                total_val  = df_cl["valor_clp"].sum()
                total_cost = df_cl["costo_clp"].sum()
                total_gan  = df_cl["ganancia_clp"].sum()
                total_ret  = (total_gan / total_cost * 100) if total_cost else 0

                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Valor de mercado", fmt_clp(total_val))
                with c2: st.metric("Costo total", fmt_clp(total_cost))
                with c3: st.metric("Ganancia/Pérdida", fmt_clp(total_gan), delta=fmt_pct(total_ret))
                with c4: st.metric("Posiciones", str(len(df_cl)))

                st.divider()
                section_title("Mapa de posiciones")
                fig = px.treemap(
                    df_cl, path=["ticker"], values="valor_clp",
                    color="retorno_pct",
                    color_continuous_scale=["#e74c3c","#f39c12","#2ecc71"],
                    color_continuous_midpoint=0,
                    custom_data=["empresa","ganancia_clp"],
                )
                fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f}")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)

                section_title("Detalle")
                tbl = df_cl[["ticker","empresa","cantidad","precio_compra","precio_actual","costo_clp","valor_clp","ganancia_clp","retorno_pct"]].copy()
                tbl["precio_compra"] = tbl["precio_compra"].apply(lambda x: fmt_clp(x,2))
                tbl["precio_actual"] = tbl["precio_actual"].apply(lambda x: fmt_clp(x,2))
                tbl["costo_clp"]     = tbl["costo_clp"].apply(fmt_clp)
                tbl["valor_clp"]     = tbl["valor_clp"].apply(fmt_clp)
                tbl["ganancia_clp"]  = tbl["ganancia_clp"].apply(fmt_clp)
                tbl["retorno_pct"]   = tbl["retorno_pct"].apply(fmt_pct)
                tbl.columns = ["Ticker","Empresa","Cantidad","P. Compra","P. Actual","Costo CLP","Valor CLP","Ganancia","Retorno %"]
                st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 3: INTERNACIONAL
    # ────────────────────────────────────────────────────────
    with tab3:
        if df_cartera.empty:
            st.info("Sin datos.")
        else:
            df = _enrich(df_cartera)
            df_i = df[df["mercado"].isin(["internacional","crypto"])].copy()
            if df_i.empty:
                st.info("Sin posiciones internacionales.")
            else:
                total_val_usd  = df_i[df_i["moneda"]=="USD"]["valor_usd"].sum()
                total_cost_usd = df_i[df_i["moneda"]=="USD"]["costo_usd"].sum()
                total_val_clp  = df_i["valor_clp"].sum()
                total_gan_clp  = df_i["ganancia_clp"].sum()
                total_ret      = (total_gan_clp / df_i["costo_clp"].sum() * 100) if df_i["costo_clp"].sum() else 0

                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Valor (USD)", fmt_usd(total_val_usd, 0), help=fmt_clp(total_val_clp))
                with c2: st.metric("Costo (USD)", fmt_usd(total_cost_usd, 0))
                with c3: st.metric("Ganancia", fmt_usd(total_gan_clp/USD_CLP, 0), delta=fmt_pct(total_ret))
                with c4: st.metric("Posiciones", str(len(df_i)))

                st.divider()
                buscar = st.text_input("🔍 Buscar", "", key="intl_buscar")
                if buscar:
                    df_i = df_i[df_i["ticker"].str.contains(buscar.upper(), na=False) |
                                df_i["empresa"].str.contains(buscar, case=False, na=False)]

                section_title("Mapa de posiciones (top 15)")
                top15 = df_i.nlargest(15, "valor_clp")
                fig = px.treemap(
                    top15, path=["tipo","ticker"], values="valor_clp",
                    color="retorno_pct",
                    color_continuous_scale=["#e74c3c","#f39c12","#2ecc71"],
                    color_continuous_midpoint=0,
                    custom_data=["empresa"],
                )
                fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f}")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10), height=320)
                st.plotly_chart(fig, use_container_width=True)

                section_title(f"Detalle ({len(df_i)} posiciones)")
                df_i = df_i.sort_values("valor_clp", ascending=False)
                tbl = df_i[["ticker","empresa","tipo","pais","cantidad","precio_actual","valor_usd","valor_clp","ganancia_clp","retorno_pct"]].copy()
                tbl["precio_actual"] = tbl.apply(lambda r: f"${r['precio_actual']:,.2f}", axis=1)
                tbl["valor_usd"]     = tbl["valor_usd"].apply(lambda x: fmt_usd(x,0))
                tbl["valor_clp"]     = tbl["valor_clp"].apply(fmt_clp)
                tbl["ganancia_clp"]  = tbl["ganancia_clp"].apply(fmt_clp)
                tbl["retorno_pct"]   = tbl["retorno_pct"].apply(fmt_pct)
                tbl.columns = ["Ticker","Empresa","Tipo","País","Cantidad","P. Actual","Valor USD","Valor CLP","Ganancia CLP","Retorno %"]
                st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 4: HISTORIAL RACIONAL
    # ────────────────────────────────────────────────────────
    with tab4:
        if df_racional.empty:
            st.info("Sin transacciones.")
        else:
            df_r = df_racional.copy()
            df_r["monto_clp"] = pd.to_numeric(df_r.get("monto_clp", 0), errors="coerce")

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Transacciones", str(len(df_r)))
            with c2: st.metric("Total invertido CLP", fmt_clp(df_r["monto_clp"].sum()))
            with c3:
                if "ticker" in df_r.columns:
                    st.metric("Tickers únicos", str(df_r["ticker"].nunique()))

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                mercados = ["Todos"] + sorted(df_r["mercado"].dropna().unique().tolist())
                m_sel = st.selectbox("Mercado", mercados, key="hist_m")
            with col_f2:
                if "ticker" in df_r.columns:
                    tks = ["Todos"] + sorted(df_r["ticker"].dropna().unique().tolist())
                    tk_sel = st.selectbox("Ticker", tks, key="hist_tk")
                else:
                    tk_sel = "Todos"

            df_rf = df_r.copy()
            if m_sel != "Todos": df_rf = df_rf[df_rf["mercado"] == m_sel]
            if tk_sel != "Todos" and "ticker" in df_rf.columns: df_rf = df_rf[df_rf["ticker"] == tk_sel]

            show_cols = [c for c in ["fecha","mercado","tipo","ticker","acciones","precio","monto_clp","monto_usd"] if c in df_rf.columns]
            tbl = df_rf[show_cols].copy().sort_values("fecha", ascending=False)
            if "fecha" in tbl.columns: tbl["fecha"] = pd.to_datetime(tbl["fecha"]).dt.strftime("%Y-%m-%d")
            if "monto_clp" in tbl.columns: tbl["monto_clp"] = tbl["monto_clp"].apply(fmt_clp)
            if "monto_usd" in tbl.columns: tbl["monto_usd"] = pd.to_numeric(tbl["monto_usd"], errors="coerce").apply(lambda x: fmt_usd(x,2) if pd.notna(x) else "-")
            tbl.columns = [c.replace("_"," ").title() for c in tbl.columns]
            st.dataframe(tbl, hide_index=True, use_container_width=True)
