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
from dashboard.mappings import get_tipo, get_pais, get_sector

USD_CLP = get_usd_clp()

# ── Escala de color con contraste real (rojo-blanco-verde) ──
HEAT_SCALE = [
    [0.00, "#8b0000"],   # rojo oscuro   → muy negativo
    [0.35, "#e74c3c"],   # rojo          → negativo
    [0.50, "#e8e8e8"],   # gris claro    → 0%
    [0.65, "#2ecc71"],   # verde         → positivo
    [1.00, "#1a6b35"],   # verde oscuro  → muy positivo
]
HEAT_RANGE = [-40, 60]   # rango fijo para que 0 siempre sea gris


@st.cache_data(ttl=14400, show_spinner=False)   # cache 4 horas
def _fetch_metrics(yf_tickers: tuple) -> pd.DataFrame:
    """
    Obtiene P/E, EPS y Dividend Yield via yfinance.
    yf_tickers: en formato yfinance (e.g. BCI.SN para Santiago, VT para NYSE).
    Retorna DataFrame con 'ticker' en formato original (sin sufijo .SN).
    """
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame(columns=["ticker","pe","eps","div_yield"])

    rows = []
    for tk in yf_tickers:
        tk_key = tk[:-3] if tk.endswith(".SN") else tk   # clave original sin sufijo
        try:
            info = yf.Ticker(tk).info
            rows.append({
                "ticker":    tk_key,
                "pe":        info.get("trailingPE"),
                "eps":       info.get("trailingEps"),
                "div_yield": (info.get("dividendYield") or 0) * 100,
            })
        except Exception:
            rows.append({"ticker": tk_key, "pe": None, "eps": None, "div_yield": None})
    return pd.DataFrame(rows)


def _enrich(df):
    df = df.copy()
    df["tipo"]   = df.apply(lambda r: get_tipo(r["ticker"], r.get("mercado", "")), axis=1)
    df["pais"]   = df.apply(lambda r: get_pais(r["ticker"], r.get("mercado", "")), axis=1)
    df["sector"] = df.apply(lambda r: get_sector(r["ticker"], r.get("tipo", "")), axis=1)
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Consolidado",
        "🇨🇱 Acciones Chile",
        "🌎 Internacional",
        "📊 Historial Racional",
        "🔬 Fundamentos",
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
                color_continuous_scale=HEAT_SCALE,
                color_continuous_midpoint=0,
                range_color=HEAT_RANGE,
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

                freq = freq_map[periodo]
                period_key = {"W":"W","ME":"M","QE":"Q","YE":"Y"}[freq]
                df_r["_period"] = df_r["fecha"].dt.to_period(period_key)

                if periodo == "Semana":
                    # Formato "W10-23" (semana ISO 10 del año 2023)
                    df_r["periodo"] = df_r["_period"].apply(
                        lambda p: f"W{p.start_time.strftime('%V-%y')}"
                    )
                elif periodo == "Quarter":
                    df_r["periodo"] = df_r["_period"].apply(
                        lambda p: f"Q{p.quarter} {p.year}"
                    )
                else:
                    df_r["periodo"] = df_r["_period"].astype(str)

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

            # ── Gráfico por sector / industria ───────────────
            st.divider()
            section_title("Distribución por sector / industria")

            df_sector = df_f.copy()
            grp_sector = (df_sector.groupby(["tipo", "sector"])["valor_clp"]
                          .sum().reset_index())
            grp_sector = grp_sector[grp_sector["valor_clp"] > 0]

            fig_sec = px.sunburst(
                grp_sector,
                path=["tipo", "sector"],
                values="valor_clp",
                color="tipo",
                color_discrete_sequence=ASSET_COLORS,
            )
            fig_sec.update_traces(
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} CLP<br>%{percentParent:.1%} del tipo<extra></extra>",
                textinfo="label+percent entry",
            )
            fig_sec.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=420,
                font_color="#ccd6f6",
            )
            st.plotly_chart(fig_sec, use_container_width=True)

            # Tabla sector
            grp_sec_tbl = (df_f.groupby("sector")["valor_clp"]
                           .agg(Valor="sum", Posiciones="count")
                           .reset_index().sort_values("Valor", ascending=False))
            grp_sec_tbl["% Cartera"] = (grp_sec_tbl["Valor"] / df_f["valor_clp"].sum() * 100).round(1).astype(str) + "%"
            grp_sec_tbl["Valor"] = grp_sec_tbl["Valor"].apply(fmt_clp)
            grp_sec_tbl.columns = ["Sector", "Valor CLP", "Posiciones", "% Cartera"]
            st.dataframe(grp_sec_tbl, hide_index=True, use_container_width=True)

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
                tbl["precio_actual"] = tbl["precio_actual"].apply(lambda x: fmt_usd(x, 2))
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
            df_r["monto_usd"] = pd.to_numeric(df_r.get("monto_usd", pd.Series(dtype=float)), errors="coerce")
            df_r["monto_clp"] = pd.to_numeric(df_r.get("monto_clp", pd.Series(dtype=float)), errors="coerce")
            # Monto efectivo en USD (ventas en negativo)
            df_r["monto_usd_ef"] = df_r.apply(
                lambda r: r["monto_usd"] if pd.notna(r["monto_usd"])
                          else (r["monto_clp"] / USD_CLP if pd.notna(r["monto_clp"]) else 0),
                axis=1
            )

            compras_usd = df_r[df_r["tipo"]=="compra"]["monto_usd_ef"].sum()
            ventas_usd  = df_r[df_r["tipo"]=="venta"]["monto_usd_ef"].sum()
            neto_usd    = compras_usd - ventas_usd

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Compras (USD)", fmt_usd(compras_usd, 0))
            with c2: st.metric("Ventas (USD)",  fmt_usd(ventas_usd, 0))
            with c3: st.metric("Inversión neta (USD)", fmt_usd(neto_usd, 0),
                                help="Lo realmente puesto de tu bolsillo")
            with c4: st.metric("Tickers únicos", str(df_r["ticker"].nunique()) if "ticker" in df_r.columns else "-")

            st.divider()

            # Gráfico compras vs ventas por mes
            section_title("Flujo mensual: compras vs ventas")
            df_r["_mes"] = pd.to_datetime(df_r["fecha"]).dt.to_period("M").astype(str)
            grp_cv = df_r.groupby(["_mes","tipo"])["monto_usd_ef"].sum().reset_index()
            grp_cv["monto_plot"] = grp_cv.apply(
                lambda r: r["monto_usd_ef"] if r["tipo"]=="compra" else -r["monto_usd_ef"], axis=1
            )
            fig_cv = px.bar(
                grp_cv, x="_mes", y="monto_plot", color="tipo",
                barmode="relative",
                color_discrete_map={"compra": "#4e79a7", "venta": "#e15759"},
                labels={"_mes": "", "monto_plot": "USD", "tipo": ""},
            )
            fig_cv.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccd6f6", margin=dict(t=10,b=10,l=10,r=10), height=280,
                xaxis=dict(showgrid=False, tickangle=-45),
                yaxis=dict(gridcolor="#2d3250", tickprefix="$"),
                legend=dict(orientation="h", y=1.1),
            )
            st.plotly_chart(fig_cv, use_container_width=True)

            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                tipo_ops = ["Todos", "compra", "venta"]
                tipo_sel2 = st.selectbox("Tipo", tipo_ops, key="hist_tipo")
            with col_f2:
                mercados = ["Todos"] + sorted(df_r["mercado"].dropna().unique().tolist())
                m_sel = st.selectbox("Mercado", mercados, key="hist_m")
            with col_f3:
                if "ticker" in df_r.columns:
                    tks = ["Todos"] + sorted(df_r["ticker"].dropna().unique().tolist())
                    tk_sel = st.selectbox("Ticker", tks, key="hist_tk")
                else:
                    tk_sel = "Todos"

            df_rf = df_r.copy()
            if tipo_sel2 != "Todos": df_rf = df_rf[df_rf["tipo"] == tipo_sel2]
            if m_sel != "Todos": df_rf = df_rf[df_rf["mercado"] == m_sel]
            if tk_sel != "Todos" and "ticker" in df_rf.columns: df_rf = df_rf[df_rf["ticker"] == tk_sel]

            section_title(f"Detalle transacciones ({len(df_rf)})")
            show_cols = [c for c in ["fecha","tipo","mercado","ticker","empresa","acciones","precio_usd","monto_usd"] if c in df_rf.columns]
            tbl = df_rf[show_cols].copy().sort_values("fecha", ascending=False)
            if "fecha" in tbl.columns: tbl["fecha"] = pd.to_datetime(tbl["fecha"]).dt.strftime("%Y-%m-%d")
            if "monto_usd" in tbl.columns: tbl["monto_usd"] = pd.to_numeric(tbl["monto_usd"], errors="coerce").apply(lambda x: fmt_usd(x,2) if pd.notna(x) else "-")
            if "precio_usd" in tbl.columns: tbl["precio_usd"] = pd.to_numeric(tbl["precio_usd"], errors="coerce").apply(lambda x: fmt_usd(x,2) if pd.notna(x) else "-")
            tbl.columns = [c.replace("_"," ").title() for c in tbl.columns]
            st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 5: FUNDAMENTOS
    # ────────────────────────────────────────────────────────
    with tab5:
        if df_cartera.empty:
            st.info("Sin datos.")
        else:
            df = _enrich(df_cartera)

            # Filtros
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                tipos = ["Todos"] + sorted(df["tipo"].dropna().unique().tolist())
                tipo_sel = st.selectbox("Tipo", tipos, key="fund_tipo")
            with col_f2:
                paises = ["Todos"] + sorted(df["pais"].dropna().unique().tolist())
                pais_sel = st.selectbox("País", paises, key="fund_pais")

            # Filtro adicional: sector
            with st.columns(1)[0]:
                sectores = ["Todos"] + sorted(df["sector"].dropna().unique().tolist())
                sector_sel = st.selectbox("Sector / Industria", sectores, key="fund_sector")

            df_f = df.copy()
            if tipo_sel   != "Todos": df_f = df_f[df_f["tipo"]   == tipo_sel]
            if pais_sel   != "Todos": df_f = df_f[df_f["pais"]   == pais_sel]
            if sector_sel != "Todos": df_f = df_f[df_f["sector"] == sector_sel]

            # ── Tickers en formato yfinance ──────────────────
            # Acciones chilenas necesitan sufijo .SN (Bolsa de Santiago)
            yf_map = {
                row["ticker"]: (f"{row['ticker']}.SN" if row.get("mercado") == "nacional" else row["ticker"])
                for _, row in df_f.drop_duplicates("ticker").iterrows()
                if pd.notna(row["ticker"])
            }
            yf_tickers = tuple(sorted(set(yf_map.values())))

            with st.spinner(f"Cargando métricas para {len(yf_tickers)} tickers…"):
                metrics = _fetch_metrics(yf_tickers)

            if metrics.empty:
                st.warning("No se pudieron cargar métricas. Verifica conexión a internet.")
            else:
                df_m = df_f.merge(metrics, on="ticker", how="left")

                # ── KPIs ponderados ───────────────────────────
                st.divider()
                section_title("Promedios ponderados por valor de cartera")

                total_val = df_m["valor_clp"].sum()

                def wavg(col):
                    sub = df_m[df_m[col].notna()]
                    if sub.empty: return None
                    w = sub["valor_clp"] / sub["valor_clp"].sum()
                    return (sub[col] * w).sum()

                avg_pe  = wavg("pe")
                avg_eps = wavg("eps")
                avg_div = wavg("div_yield")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("P/E promedio ponderado",
                              f"{avg_pe:.1f}x" if avg_pe else "—",
                              help="<15 barato · 15–25 normal · >25 caro")
                with c2:
                    st.metric("EPS promedio ponderado",
                              f"{avg_eps:.2f}" if avg_eps else "—",
                              help="Earnings Per Share trailing 12m (moneda local del activo)")
                with c3:
                    st.metric("Dividend Yield promedio",
                              f"{avg_div:.2f}%" if avg_div is not None else "—",
                              help="Rendimiento por dividendos anual sobre precio actual")

                st.divider()

                # ── Gráfico burbuja: P/E vs EPS ───────────────
                section_title("Mapa de valoración: P/E vs EPS")
                st.caption("Cuadrante ideal → P/E bajo + EPS alto = acción subvalorada con buenas ganancias. Tamaño de burbuja = valor en cartera.")

                df_bub = df_m[df_m["pe"].notna() & df_m["eps"].notna()].copy()

                if not df_bub.empty:
                    df_bub["hover_txt"] = df_bub.apply(
                        lambda r: (
                            f"<b>{r['ticker']}</b> — {r.get('empresa','')}<br>"
                            f"Tipo: {r['tipo']} | Sector: {r['sector']}<br>"
                            f"P/E: {r['pe']:.1f}x | EPS: {r['eps']:.2f}<br>"
                            f"Div Yield: {r['div_yield']:.2f}%<br>"
                            f"Valor cartera: {fmt_clp(r['valor_clp'])}"
                        ), axis=1
                    )
                    fig_bub = px.scatter(
                        df_bub,
                        x="pe", y="eps",
                        size="valor_clp", size_max=60,
                        color="sector",
                        text="ticker",
                        color_discrete_sequence=ASSET_COLORS,
                        labels={"pe": "P/E Ratio", "eps": "EPS (moneda local)", "sector": "Sector"},
                        custom_data=["hover_txt"],
                    )
                    fig_bub.update_traces(
                        hovertemplate="%{customdata[0]}<extra></extra>",
                        textposition="top center",
                        textfont=dict(size=9),
                    )
                    fig_bub.add_vline(x=15, line_dash="dot", line_color="#2ecc71",
                                      annotation_text="P/E 15 (barato)", annotation_position="top right",
                                      annotation_font_color="#2ecc71")
                    fig_bub.add_vline(x=25, line_dash="dot", line_color="#e74c3c",
                                      annotation_text="P/E 25 (caro)", annotation_position="top right",
                                      annotation_font_color="#e74c3c")
                    fig_bub.add_hline(y=0, line_color="#888", line_width=1)
                    fig_bub.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#ccd6f6",
                        margin=dict(t=20, b=10, l=10, r=10), height=460,
                        xaxis=dict(gridcolor="#2d3250", title="P/E Ratio  (← más barato)"),
                        yaxis=dict(gridcolor="#2d3250", title="EPS  (más rentable →)"),
                        legend=dict(orientation="v", x=1.01),
                    )
                    st.plotly_chart(fig_bub, use_container_width=True)
                else:
                    st.info("No hay suficientes datos P/E + EPS para este filtro.")

                st.divider()

                # ── Barra P/E comparativo ─────────────────────
                section_title("Comparativo P/E por posición")

                df_pe = df_m[df_m["pe"].notna()].sort_values("pe").copy()
                if not df_pe.empty:
                    df_pe["color_pe"] = df_pe["pe"].apply(
                        lambda x: "#2ecc71" if x < 15 else ("#f39c12" if x < 25 else "#e74c3c")
                    )
                    df_pe["hover_pe"] = df_pe.apply(
                        lambda r: (
                            f"<b>{r['ticker']}</b><br>"
                            f"P/E: {r['pe']:.1f}x | EPS: {r['eps']:.2f if pd.notna(r['eps']) else '—'}<br>"
                            f"Div Yield: {r['div_yield']:.2f}%<br>"
                            f"Valor: {fmt_clp(r['valor_clp'])}"
                        ), axis=1
                    )
                    fig_pe = go.Figure(go.Bar(
                        x=df_pe["pe"], y=df_pe["ticker"],
                        orientation="h",
                        marker_color=df_pe["color_pe"],
                        text=df_pe["pe"].apply(lambda x: f"{x:.1f}x"),
                        textposition="outside",
                        customdata=df_pe[["hover_pe"]].values,
                        hovertemplate="%{customdata[0]}<extra></extra>",
                    ))
                    fig_pe.add_vline(x=15, line_dash="dot", line_color="#2ecc71",
                                     annotation_text="15x", annotation_font_color="#2ecc71")
                    fig_pe.add_vline(x=25, line_dash="dot", line_color="#e74c3c",
                                     annotation_text="25x", annotation_font_color="#e74c3c")
                    fig_pe.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#ccd6f6",
                        margin=dict(t=20, b=10, l=10, r=60),
                        height=max(300, len(df_pe) * 28),
                        xaxis=dict(gridcolor="#2d3250", title="P/E Ratio"),
                        yaxis=dict(showgrid=False),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_pe, use_container_width=True)
                    st.caption("🟢 P/E < 15 (barato) · 🟡 15–25 (normal) · 🔴 > 25 (caro)")

                st.divider()

                # ── Tabla detalle ─────────────────────────────
                section_title("Detalle por ticker")

                tbl = df_m[[
                    "ticker", "empresa", "tipo", "pais", "sector",
                    "valor_clp", "retorno_pct", "pe", "eps", "div_yield"
                ]].copy().sort_values("valor_clp", ascending=False)

                tbl["valor_clp"]   = tbl["valor_clp"].apply(fmt_clp)
                tbl["retorno_pct"] = tbl["retorno_pct"].apply(fmt_pct)
                tbl["pe"]          = tbl["pe"].apply(lambda x: f"{x:.1f}x" if pd.notna(x) else "—")
                tbl["eps"]         = tbl["eps"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
                tbl["div_yield"]   = tbl["div_yield"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")

                tbl.columns = ["Ticker", "Empresa", "Tipo", "País", "Sector",
                               "Valor CLP", "Retorno %", "P/E", "EPS", "Div Yield"]
                st.dataframe(tbl, hide_index=True, use_container_width=True)

                st.caption("📡 Datos vía Yahoo Finance · Caché 4h · Trailing 12m · Acciones Chile: sufijo .SN (Bolsa de Santiago)")
