# ============================================================
# VISTA: INVERSIONES
# ============================================================

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, fmt_pct,
    section_title, ASSET_COLORS,
    load_cartera, load_racional, load_buda, get_usd_clp,
)


def render():
    st.title("📈 Inversiones")

    usd_clp = get_usd_clp()
    df_cartera = load_cartera()
    df_racional = load_racional()
    df_buda = load_buda()

    tab1, tab2, tab3, tab4 = st.tabs([
        "🇨🇱 Acciones Chile",
        "🌎 Stocks Internacionales",
        "₿ Crypto (Buda)",
        "📋 Historial Transacciones"
    ])

    # ────────────────────────────────────────────────────────
    # TAB 1: ACCIONES CHILENAS
    # ────────────────────────────────────────────────────────
    with tab1:
        if df_cartera.empty:
            st.info("No hay datos de cartera.")
        else:
            df_cl = df_cartera[df_cartera["mercado"] == "nacional"].copy()
            if df_cl.empty:
                st.info("Sin posiciones chilenas.")
            else:
                df_cl["valor_actual"] = df_cl["cantidad"] * df_cl["precio_actual"]
                df_cl["costo_total"]  = df_cl["cantidad"] * df_cl["precio_compra"]
                df_cl["ganancia"]     = df_cl["valor_actual"] - df_cl["costo_total"]
                df_cl["retorno_pct"]  = (df_cl["ganancia"] / df_cl["costo_total"] * 100).round(2)
                df_cl = df_cl.sort_values("valor_actual", ascending=False)

                total_val  = df_cl["valor_actual"].sum()
                total_cost = df_cl["costo_total"].sum()
                total_gan  = df_cl["ganancia"].sum()
                total_ret  = (total_gan / total_cost * 100) if total_cost else 0

                # KPIs
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Valor de mercado", fmt_clp(total_val))
                with c2:
                    st.metric("Costo total", fmt_clp(total_cost))
                with c3:
                    st.metric("Ganancia/Pérdida", fmt_clp(total_gan),
                              delta=fmt_pct(total_ret))
                with c4:
                    st.metric("N° posiciones", str(len(df_cl)))

                st.divider()

                # Gráfico treemap
                section_title("Mapa de posiciones (por valor actual)")
                fig = px.treemap(
                    df_cl,
                    path=["ticker"],
                    values="valor_actual",
                    color="retorno_pct",
                    color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                    color_continuous_midpoint=0,
                    custom_data=["empresa", "ganancia"],
                )
                fig.update_traces(
                    texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{value:,.0f}",
                    hovertemplate="<b>%{label}</b><br>Valor: %{value:,.0f}<br>Ganancia: %{customdata[1]:,.0f}<extra></extra>",
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=350,
                    coloraxis_colorbar=dict(title="Retorno %"),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Tabla detalle
                section_title("Detalle de posiciones")
                show = df_cl[[
                    "ticker", "empresa", "cantidad",
                    "precio_compra", "precio_actual",
                    "costo_total", "valor_actual",
                    "ganancia", "retorno_pct"
                ]].copy()
                show.columns = [
                    "Ticker", "Empresa", "Cantidad",
                    "P. Compra", "P. Actual",
                    "Costo Total", "Valor Actual",
                    "Ganancia", "Retorno %"
                ]
                show["P. Compra"]   = show["P. Compra"].apply(lambda x: fmt_clp(x, 2))
                show["P. Actual"]   = show["P. Actual"].apply(lambda x: fmt_clp(x, 2))
                show["Costo Total"] = show["Costo Total"].apply(fmt_clp)
                show["Valor Actual"]= show["Valor Actual"].apply(fmt_clp)
                show["Ganancia"]    = show["Ganancia"].apply(fmt_clp)
                show["Retorno %"]   = show["Retorno %"].apply(fmt_pct)
                st.dataframe(show, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 2: STOCKS INTERNACIONALES
    # ────────────────────────────────────────────────────────
    with tab2:
        if df_cartera.empty:
            st.info("No hay datos de cartera.")
        else:
            df_intl = df_cartera[df_cartera["mercado"] == "internacional"].copy()
            if df_intl.empty:
                st.info("Sin posiciones internacionales.")
            else:
                df_intl["valor_usd"]    = df_intl["cantidad"] * df_intl["precio_actual"]
                df_intl["costo_usd"]    = df_intl["cantidad"] * df_intl["precio_compra"]
                df_intl["ganancia_usd"] = df_intl["valor_usd"] - df_intl["costo_usd"]
                df_intl["retorno_pct"]  = (df_intl["ganancia_usd"] / df_intl["costo_usd"] * 100).round(2)
                df_intl = df_intl.sort_values("valor_usd", ascending=False)

                total_val_usd  = df_intl["valor_usd"].sum()
                total_cost_usd = df_intl["costo_usd"].sum()
                total_gan_usd  = df_intl["ganancia_usd"].sum()
                total_ret      = (total_gan_usd / total_cost_usd * 100) if total_cost_usd else 0

                # KPIs
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Valor de mercado",
                              fmt_usd(total_val_usd, 0),
                              help=fmt_clp(total_val_usd * usd_clp))
                with c2:
                    st.metric("Costo total", fmt_usd(total_cost_usd, 0))
                with c3:
                    st.metric("Ganancia/Pérdida",
                              fmt_usd(total_gan_usd, 0),
                              delta=fmt_pct(total_ret))
                with c4:
                    st.metric("N° posiciones", str(len(df_intl)))

                st.divider()

                # Filtros
                col_f1, col_f2 = st.columns([2, 3])
                with col_f1:
                    buscar = st.text_input("🔍 Buscar ticker o empresa", "")
                with col_f2:
                    ordenar_por = st.selectbox(
                        "Ordenar por",
                        ["Valor USD ↓", "Ganancia USD ↓", "Retorno % ↓", "Ticker A→Z"],
                        index=0
                    )

                df_show = df_intl.copy()
                if buscar:
                    mask = (
                        df_show["ticker"].str.contains(buscar.upper(), na=False) |
                        df_show["empresa"].str.contains(buscar, case=False, na=False)
                    )
                    df_show = df_show[mask]

                sort_map = {
                    "Valor USD ↓": ("valor_usd", False),
                    "Ganancia USD ↓": ("ganancia_usd", False),
                    "Retorno % ↓": ("retorno_pct", False),
                    "Ticker A→Z": ("ticker", True),
                }
                col_s, asc_s = sort_map[ordenar_por]
                df_show = df_show.sort_values(col_s, ascending=asc_s)

                # Top 10 treemap
                section_title(f"Mapa de posiciones (top 10 por valor, {len(df_intl)} total)")
                top_tree = df_intl.head(10).copy()
                otros_val = df_intl.iloc[10:]["valor_usd"].sum()
                otros_gan = df_intl.iloc[10:]["ganancia_usd"].sum()
                otros_ret = (otros_gan / (df_intl.iloc[10:]["costo_usd"].sum()) * 100) if df_intl.iloc[10:]["costo_usd"].sum() != 0 else 0

                if otros_val > 0:
                    top_tree = pd.concat([
                        top_tree,
                        pd.DataFrame([{
                            "ticker": "Otros", "empresa": f"({len(df_intl)-10} stocks)",
                            "valor_usd": otros_val, "ganancia_usd": otros_gan,
                            "retorno_pct": round(otros_ret, 2)
                        }])
                    ], ignore_index=True)

                fig2 = px.treemap(
                    top_tree,
                    path=["ticker"],
                    values="valor_usd",
                    color="retorno_pct",
                    color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                    color_continuous_midpoint=0,
                    custom_data=["empresa", "ganancia_usd"],
                )
                fig2.update_traces(
                    texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>$%{value:,.0f}",
                )
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=350,
                )
                st.plotly_chart(fig2, use_container_width=True)

                # Tabla
                section_title(f"Detalle ({len(df_show)} posiciones)")
                tbl = df_show[[
                    "ticker", "empresa", "cantidad",
                    "precio_compra", "precio_actual",
                    "costo_usd", "valor_usd",
                    "ganancia_usd", "retorno_pct"
                ]].copy()
                tbl.columns = [
                    "Ticker", "Empresa", "Cantidad",
                    "P. Compra", "P. Actual",
                    "Costo USD", "Valor USD",
                    "Ganancia USD", "Retorno %"
                ]
                for col in ["P. Compra", "P. Actual"]:
                    tbl[col] = tbl[col].apply(lambda x: f"${x:,.2f}")
                for col in ["Costo USD", "Valor USD", "Ganancia USD"]:
                    tbl[col] = tbl[col].apply(lambda x: fmt_usd(x, 0))
                tbl["Retorno %"] = tbl["Retorno %"].apply(fmt_pct)
                st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 3: CRYPTO (BUDA)
    # ────────────────────────────────────────────────────────
    with tab3:
        if df_buda.empty:
            st.info("No hay datos de crypto.")
        else:
            df_b = df_buda.copy()

            # KPIs
            total_comprado = pd.to_numeric(df_b.get("monto_clp", pd.Series([0])), errors="coerce").sum()
            n_ops = len(df_b)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total comprado (costo base)", fmt_clp(total_comprado))
            with c2:
                st.metric("Operaciones registradas", str(n_ops))

            st.divider()

            # Tabla transacciones
            section_title("Compras de crypto")
            show_cols = [c for c in ["fecha", "activo", "cantidad", "precio_usd", "monto_clp"] if c in df_b.columns]
            tbl_b = df_b[show_cols].copy().sort_values("fecha", ascending=False)

            rename_map = {
                "fecha": "Fecha", "activo": "Activo",
                "cantidad": "Cantidad", "precio_usd": "Precio USD",
                "monto_clp": "Monto CLP"
            }
            tbl_b.rename(columns={k: v for k, v in rename_map.items() if k in tbl_b.columns}, inplace=True)

            if "Monto CLP" in tbl_b.columns:
                tbl_b["Monto CLP"] = pd.to_numeric(tbl_b["Monto CLP"], errors="coerce").apply(fmt_clp)
            if "Precio USD" in tbl_b.columns:
                tbl_b["Precio USD"] = pd.to_numeric(tbl_b["Precio USD"], errors="coerce").apply(lambda x: fmt_usd(x, 2))
            if "Fecha" in tbl_b.columns:
                tbl_b["Fecha"] = tbl_b["Fecha"].dt.strftime("%Y-%m-%d")

            st.dataframe(tbl_b, hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────
    # TAB 4: HISTORIAL TRANSACCIONES RACIONAL
    # ────────────────────────────────────────────────────────
    with tab4:
        if df_racional.empty:
            st.info("No hay transacciones registradas.")
        else:
            df_r = df_racional.copy()

            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                mercados = ["Todos"] + sorted(df_r["mercado"].dropna().unique().tolist())
                mercado_sel = st.selectbox("Mercado", mercados)
            with col_f2:
                if "tipo" in df_r.columns:
                    tipos = ["Todos"] + sorted(df_r["tipo"].dropna().unique().tolist())
                    tipo_sel = st.selectbox("Tipo", tipos)
                else:
                    tipo_sel = "Todos"
            with col_f3:
                if "ticker" in df_r.columns:
                    tickers = ["Todos"] + sorted(df_r["ticker"].dropna().unique().tolist())
                    ticker_sel = st.selectbox("Ticker", tickers)
                else:
                    ticker_sel = "Todos"

            df_filt = df_r.copy()
            if mercado_sel != "Todos":
                df_filt = df_filt[df_filt["mercado"] == mercado_sel]
            if tipo_sel != "Todos" and "tipo" in df_filt.columns:
                df_filt = df_filt[df_filt["tipo"] == tipo_sel]
            if ticker_sel != "Todos" and "ticker" in df_filt.columns:
                df_filt = df_filt[df_filt["ticker"] == ticker_sel]

            st.markdown(f"**{len(df_filt)} transacciones**")

            show_cols_r = [c for c in ["fecha", "mercado", "tipo", "ticker", "acciones", "precio", "monto_clp", "monto_usd"] if c in df_filt.columns]
            tbl_r = df_filt[show_cols_r].copy().sort_values("fecha", ascending=False)

            if "fecha" in tbl_r.columns:
                tbl_r["fecha"] = tbl_r["fecha"].dt.strftime("%Y-%m-%d")
            if "monto_clp" in tbl_r.columns:
                tbl_r["monto_clp"] = pd.to_numeric(tbl_r["monto_clp"], errors="coerce").apply(fmt_clp)
            if "monto_usd" in tbl_r.columns:
                tbl_r["monto_usd"] = pd.to_numeric(tbl_r["monto_usd"], errors="coerce").apply(lambda x: fmt_usd(x, 2) if pd.notna(x) else "-")
            if "precio" in tbl_r.columns:
                tbl_r["precio"] = pd.to_numeric(tbl_r["precio"], errors="coerce").apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")

            tbl_r.columns = [c.replace("_", " ").title() for c in tbl_r.columns]
            st.dataframe(tbl_r, hide_index=True, use_container_width=True)

            # Evolución del gasto mensual
            if not df_r.empty and "monto_clp" in df_r.columns:
                st.divider()
                section_title("Inversión mensual (Racional)")
                df_mensual = df_r.copy()
                df_mensual["mes"] = df_mensual["fecha"].dt.to_period("M").astype(str)
                df_mensual["monto_clp"] = pd.to_numeric(df_mensual["monto_clp"], errors="coerce")
                grp = df_mensual.groupby(["mes", "mercado"])["monto_clp"].sum().reset_index()

                fig = px.bar(
                    grp,
                    x="mes", y="monto_clp",
                    color="mercado",
                    barmode="stack",
                    labels={"mes": "", "monto_clp": "CLP", "mercado": "Mercado"},
                    color_discrete_map={"nacional": "#4e79a7", "internacional": "#f28e2b"},
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#ccd6f6",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=300,
                    xaxis=dict(showgrid=False),
                    yaxis=dict(gridcolor="#2d3250"),
                )
                st.plotly_chart(fig, use_container_width=True)
