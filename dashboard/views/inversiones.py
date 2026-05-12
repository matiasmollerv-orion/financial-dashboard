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
    fmt_clp_safe, fmt_usd_safe, metric_safe, amounts_hidden,
    section_title, ASSET_COLORS,
    load_cartera, load_racional, load_buda, get_usd_clp,
)
from dashboard.mappings import get_tipo, get_pais, get_sector

USD_CLP = get_usd_clp()

# ── Escala de color con contraste real (rojo-blanco-verde) ──
HEAT_SCALE = [
    [0.00, "#8b0000"],   # -40% → rojo oscuro
    [0.25, "#e74c3c"],   # -10% → rojo
    [0.40, "#e8e8e8"],   #   0% → gris neutro  ← posición exacta de 0 en rango [-40,60]
    [0.58, "#2ecc71"],   # +11% → verde
    [1.00, "#1a6b35"],   # +60% → verde oscuro
]
HEAT_RANGE = [-40, 60]   # 0% ↔ posición 40/100 = 0.40 en la escala


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_price_history(yf_tickers: tuple, lookback: str = "1y") -> pd.DataFrame:
    """
    Descarga histórico de precios ajustados (Close) para los tickers dados.
    yf_tickers debe estar en formato yfinance (con .SN para Chile).
    Retorna DataFrame con columnas = tickers yf, index = fecha.
    """
    try:
        import yfinance as yf
        tks = list(yf_tickers)
        raw = yf.download(tks, period=lookback, interval="1d",
                          auto_adjust=True, progress=False, group_by="ticker")
        if raw.empty:
            return pd.DataFrame()
        if len(tks) == 1:
            # Un solo ticker → columnas planas
            close = raw[["Close"]].copy()
            close.columns = [tks[0]]
        else:
            # MultiIndex (ticker, campo) → extraer "Close"
            close = raw.xs("Close", axis=1, level=1) if ("Close" in raw.columns.get_level_values(1)) \
                    else raw.xs("Close", axis=1, level=0)
        close.index = pd.to_datetime(close.index)
        return close
    except Exception:
        return pd.DataFrame()


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
            with c1: metric_safe("Valor total", fmt_clp(total_val))
            with c2: metric_safe("Total invertido", fmt_clp(total_cost))
            with c3: metric_safe("Ganancia / Pérdida", fmt_clp(total_gan), delta=fmt_pct(total_ret))
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
            df_f["_val_fmt"] = df_f["valor_clp"].apply(fmt_clp)
            df_f["_gan_fmt"] = df_f["ganancia_clp"].apply(fmt_clp)
            df_f["_ret_fmt"] = df_f["retorno_pct"].apply(fmt_pct)
            fig = px.treemap(
                df_f,
                path=["tipo", "ticker"],
                values="valor_clp",
                color="retorno_pct",
                color_continuous_scale=HEAT_SCALE,
                color_continuous_midpoint=0,
                range_color=HEAT_RANGE,
                custom_data=["empresa", "_val_fmt", "_gan_fmt", "_ret_fmt"],
            )
            fig.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[1]}<br>%{customdata[3]}",
                hovertemplate=(
                    "<b>%{label}</b><br>%{customdata[0]}<br>"
                    "Valor: %{customdata[1]}<br>"
                    "Ganancia: %{customdata[2]}<br>"
                    "Retorno: %{customdata[3]}"
                    "<extra></extra>"
                ),
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

                # _sort_key: fecha de inicio del período para ordenar cronológicamente
                df_r["_sort_key"] = df_r["_period"].apply(lambda p: p.start_time)

                if periodo == "Semana":
                    # "2023-W10" → ordena correctamente (año primero)
                    df_r["periodo"] = df_r["_period"].apply(
                        lambda p: f"{p.start_time.year}-W{p.start_time.strftime('%V')}"
                    )
                elif periodo == "Quarter":
                    df_r["periodo"] = df_r["_period"].apply(
                        lambda p: f"{p.year}-Q{p.quarter}"
                    )
                else:
                    df_r["periodo"] = df_r["_period"].astype(str)

                grp = df_r.groupby(["_sort_key", "periodo", "mercado"])["monto_clp"].sum().reset_index()
                grp = grp.sort_values("_sort_key")  # orden cronológico garantizado

                # Orden de categorías para que Plotly respete el orden del DataFrame
                orden_periodos = grp["periodo"].drop_duplicates().tolist()

                grp["monto_fmt"] = grp["monto_clp"].apply(fmt_clp)
                fig2 = px.bar(
                    grp,
                    x="periodo", y="monto_clp",
                    color="mercado",
                    barmode="stack",
                    category_orders={"periodo": orden_periodos},
                    labels={"periodo": "", "monto_clp": "CLP", "mercado": "Mercado"},
                    color_discrete_map={"nacional": "#4e79a7", "internacional": "#f28e2b"},
                    custom_data=["monto_fmt"],
                )
                fig2.update_traces(
                    hovertemplate="<b>%{x}</b><br>%{customdata[0]}<extra></extra>",
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

            # ── Gráfico P&L por período (precios de mercado) ──
            st.divider()
            section_title("📊 P&L por período (precios de mercado)")
            st.caption("Ganancia/pérdida de cada activo en el período, basada en precio de apertura y cierre. Usa cantidad actual como aproximación.")

            col_pnl1, col_pnl2, col_pnl3 = st.columns(3)
            with col_pnl1:
                pnl_periodo = st.radio(
                    "Período", ["Semana", "Mes", "Quarter", "Año"],
                    horizontal=True, key="pnl_periodo"
                )
            with col_pnl2:
                pnl_group = st.selectbox(
                    "Agrupar por", ["Tipo", "Sector", "Ticker"],
                    key="pnl_group"
                )
            with col_pnl3:
                pnl_lookback = st.selectbox(
                    "Histórico", ["6mo", "1y", "2y", "5y"],
                    index=1, key="pnl_lookback"
                )

            try:
                df_pnl_pos = _enrich(df_cartera)
                # Construir yf_map con .SN para Chile
                yf_map_pnl = {
                    row["ticker"]: (f"{row['ticker']}.SN" if row.get("mercado") == "nacional" else row["ticker"])
                    for _, row in df_pnl_pos.drop_duplicates("ticker").iterrows()
                    if pd.notna(row.get("ticker"))
                }
                yf_tickers_pnl = tuple(sorted(set(yf_map_pnl.values())))

                with st.spinner(f"Descargando precios históricos ({len(yf_tickers_pnl)} tickers)…"):
                    hist = _fetch_price_history(yf_tickers_pnl, pnl_lookback)

                if hist.empty:
                    st.warning("No se pudieron descargar precios históricos. Verifica conexión.")
                else:
                    # Frecuencia de resample
                    freq_map_pnl = {"Semana": "W", "Mes": "ME", "Quarter": "QE", "Año": "YE"}
                    period_key_pnl = {"W": "W", "ME": "M", "QE": "Q", "YE": "Y"}
                    freq_pnl = freq_map_pnl[pnl_periodo]
                    pk_pnl = period_key_pnl[freq_pnl]

                    # Calcular P&L por período y posición
                    pnl_rows_list = []
                    for _, pos_row in df_pnl_pos.iterrows():
                        tk_orig = pos_row["ticker"]
                        tk_yf   = yf_map_pnl.get(tk_orig, tk_orig)
                        qty     = pos_row.get("cantidad", 0) or 0
                        moneda  = pos_row.get("moneda", "USD")
                        tipo    = pos_row.get("tipo", "—")
                        sector  = pos_row.get("sector", "—")

                        if tk_yf not in hist.columns:
                            continue

                        prices = hist[tk_yf].dropna()
                        if prices.empty:
                            continue

                        # Resample: primer y último precio del período
                        resampled = prices.resample(freq_pnl).agg(first="first", last="last").dropna()

                        for idx_r, r_row in resampled.iterrows():
                            price_delta = r_row["last"] - r_row["first"]
                            # P&L en moneda del activo
                            pnl_local = price_delta * qty
                            # Convertir a CLP
                            pnl_clp = pnl_local if moneda == "CLP" else pnl_local * USD_CLP

                            # Formatear período
                            p = pd.Period(idx_r, pk_pnl)
                            if pk_pnl == "W":
                                p_label = f"{p.start_time.year}-W{p.start_time.strftime('%V')}"
                            elif pk_pnl == "Q":
                                p_label = f"{p.year}-Q{p.quarter}"
                            else:
                                p_label = str(p)

                            pnl_rows_list.append({
                                "periodo": p_label,
                                "_sort": p.start_time if hasattr(p, "start_time") else idx_r,
                                "ticker": tk_orig,
                                "tipo": tipo,
                                "sector": sector,
                                "pnl_clp": pnl_clp,
                            })

                    if not pnl_rows_list:
                        st.info("Sin datos de P&L para el período seleccionado.")
                    else:
                        df_pnl = pd.DataFrame(pnl_rows_list)
                        group_col = {"Tipo": "tipo", "Sector": "sector", "Ticker": "ticker"}[pnl_group]

                        grp_pnl = (df_pnl.groupby(["periodo", "_sort", group_col])["pnl_clp"]
                                   .sum().reset_index()
                                   .sort_values("_sort"))
                        grp_pnl["pnl_fmt"] = grp_pnl["pnl_clp"].apply(fmt_clp)
                        grp_pnl["color_val"] = grp_pnl["pnl_clp"].apply(lambda x: "gain" if x >= 0 else "loss")

                        orden_pnl = grp_pnl["periodo"].drop_duplicates().tolist()

                        fig_pnl = px.bar(
                            grp_pnl,
                            x="periodo", y="pnl_clp",
                            color=group_col,
                            barmode="relative",
                            category_orders={"periodo": orden_pnl},
                            custom_data=["pnl_fmt", group_col],
                            labels={"periodo": "", "pnl_clp": "P&L (CLP)", group_col: pnl_group},
                            color_discrete_sequence=ASSET_COLORS,
                        )
                        fig_pnl.update_traces(
                            hovertemplate=(
                                "<b>%{x}</b><br>"
                                "%{customdata[1]}<br>"
                                "P&L: %{customdata[0]}"
                                "<extra></extra>"
                            )
                        )
                        fig_pnl.add_hline(y=0, line_color="#888", line_width=1.5)
                        fig_pnl.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#ccd6f6",
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=400,
                            xaxis=dict(showgrid=False, tickangle=-45),
                            yaxis=dict(gridcolor="#2d3250"),
                            legend=dict(orientation="h", y=-0.3, font=dict(size=10)),
                        )
                        st.plotly_chart(fig_pnl, use_container_width=True)

                        # Tabla resumen P&L total por grupo en período seleccionado
                        pnl_total = (grp_pnl.groupby(group_col)["pnl_clp"]
                                     .sum().reset_index().sort_values("pnl_clp", ascending=False))
                        pnl_total["P&L CLP"] = pnl_total["pnl_clp"].apply(fmt_clp)
                        pnl_total["% del total"] = (
                            pnl_total["pnl_clp"] / pnl_total["pnl_clp"].abs().sum() * 100
                        ).round(1).astype(str) + "%"
                        pnl_total = pnl_total.drop(columns="pnl_clp")
                        pnl_total.columns = [pnl_group, "P&L CLP", "% Participación"]
                        st.dataframe(pnl_total, hide_index=True, use_container_width=True)

            except Exception as e:
                st.warning(f"Error al calcular P&L: {e}")

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
            tbl["valor_clp"]    = tbl["valor_clp"].apply(fmt_clp_safe)
            tbl["costo_clp"]    = tbl["costo_clp"].apply(fmt_clp_safe)
            tbl["ganancia_clp"] = tbl["ganancia_clp"].apply(fmt_clp_safe)
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
                with c1: metric_safe("Valor de mercado", fmt_clp(total_val))
                with c2: metric_safe("Costo total", fmt_clp(total_cost))
                with c3: metric_safe("Ganancia/Pérdida", fmt_clp(total_gan), delta=fmt_pct(total_ret))
                with c4: st.metric("Posiciones", str(len(df_cl)))

                st.divider()
                section_title("Mapa de posiciones")
                df_cl["_val_fmt"] = df_cl["valor_clp"].apply(fmt_clp)
                df_cl["_gan_fmt"] = df_cl["ganancia_clp"].apply(fmt_clp)
                df_cl["_ret_fmt"] = df_cl["retorno_pct"].apply(fmt_pct)
                fig = px.treemap(
                    df_cl, path=["ticker"], values="valor_clp",
                    color="retorno_pct",
                    color_continuous_scale=HEAT_SCALE,
                    color_continuous_midpoint=0,
                    range_color=HEAT_RANGE,
                    custom_data=["empresa", "_val_fmt", "_gan_fmt", "_ret_fmt"],
                )
                fig.update_traces(
                    texttemplate="<b>%{label}</b><br>%{customdata[1]}<br>%{customdata[3]}",
                    hovertemplate=(
                        "<b>%{label}</b><br>%{customdata[0]}<br>"
                        "Valor: %{customdata[1]}<br>"
                        "Ganancia: %{customdata[2]}<br>"
                        "Retorno: %{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
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
                with c1: metric_safe("Valor (USD)", fmt_usd(total_val_usd, 0), help=fmt_clp(total_val_clp))
                with c2: metric_safe("Costo (USD)", fmt_usd(total_cost_usd, 0))
                with c3: metric_safe("Ganancia", fmt_usd(total_gan_clp/USD_CLP, 0), delta=fmt_pct(total_ret))
                with c4: st.metric("Posiciones", str(len(df_i)))

                st.divider()
                buscar = st.text_input("🔍 Buscar", "", key="intl_buscar")
                if buscar:
                    df_i = df_i[df_i["ticker"].str.contains(buscar.upper(), na=False) |
                                df_i["empresa"].str.contains(buscar, case=False, na=False)]

                section_title("Mapa de posiciones (top 15)")
                top15 = df_i.nlargest(15, "valor_clp").copy()
                top15["_val_fmt"] = top15["valor_clp"].apply(fmt_clp)
                top15["_gan_fmt"] = top15["ganancia_clp"].apply(fmt_clp)
                top15["_ret_fmt"] = top15["retorno_pct"].apply(fmt_pct)
                fig = px.treemap(
                    top15, path=["tipo","ticker"], values="valor_clp",
                    color="retorno_pct",
                    color_continuous_scale=HEAT_SCALE,
                    color_continuous_midpoint=0,
                    range_color=HEAT_RANGE,
                    custom_data=["empresa", "_val_fmt", "_gan_fmt", "_ret_fmt"],
                )
                fig.update_traces(
                    texttemplate="<b>%{label}</b><br>%{customdata[1]}<br>%{customdata[3]}",
                    hovertemplate=(
                        "<b>%{label}</b><br>%{customdata[0]}<br>"
                        "Valor: %{customdata[1]}<br>"
                        "Ganancia: %{customdata[2]}<br>"
                        "Retorno: %{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
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
