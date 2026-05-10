# ============================================================
# VISTA: GASTOS (SANTANDER)
# ============================================================

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_usd, section_title,
    load_gastos, ASSET_COLORS,
)


def render():
    st.title("💳 Gastos")

    df = load_gastos()

    if df.empty:
        st.info("""
        📂 **No hay gastos cargados aún.**

        Para cargar los gastos de Santander, ejecuta en terminal:
        ```bash
        cd ~/Documents/Claude/FinancialDashboard
        source venv/bin/activate
        python load_santander.py
        ```
        O descarga tus cartolas/estados de cuenta desde el correo y sube los PDF.
        """)
        return

    # ── Filtros ───────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        años = sorted(df["fecha"].dt.year.unique(), reverse=True)
        año_sel = st.selectbox("Año", ["Todos"] + [str(a) for a in años])
    with col_f2:
        meses_map = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                     7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
        meses_disp = ["Todos"] + [meses_map[m] for m in sorted(df["fecha"].dt.month.unique())]
        mes_sel = st.selectbox("Mes", meses_disp)
    with col_f3:
        if "categoria" in df.columns:
            cats = ["Todas"] + sorted(df["categoria"].dropna().unique().tolist())
            cat_sel = st.selectbox("Categoría", cats)
        else:
            cat_sel = "Todas"

    # Aplicar filtros
    df_filt = df.copy()
    if año_sel != "Todos":
        df_filt = df_filt[df_filt["fecha"].dt.year == int(año_sel)]
    if mes_sel != "Todos":
        mes_num = {v: k for k, v in meses_map.items()}[mes_sel]
        df_filt = df_filt[df_filt["fecha"].dt.month == mes_num]
    if cat_sel != "Todas" and "categoria" in df_filt.columns:
        df_filt = df_filt[df_filt["categoria"] == cat_sel]

    if df_filt.empty:
        st.warning("No hay gastos para el período seleccionado.")
        return

    # ── KPIs ──────────────────────────────────────────────
    monto_col = "monto_clp" if "monto_clp" in df_filt.columns else "monto"
    df_filt[monto_col] = pd.to_numeric(df_filt[monto_col], errors="coerce")

    total = df_filt[monto_col].sum()
    n_ops = len(df_filt)
    prom_op = total / n_ops if n_ops else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total gastos", fmt_clp(total))
    with c2:
        st.metric("N° operaciones", str(n_ops))
    with c3:
        st.metric("Promedio por operación", fmt_clp(prom_op))

    st.divider()

    # ── Gráficos ──────────────────────────────────────────
    col_left, col_right = st.columns([1, 1])

    with col_left:
        if "categoria" in df_filt.columns:
            section_title("Gastos por categoría")
            grp_cat = df_filt.groupby("categoria")[monto_col].sum().reset_index()
            grp_cat = grp_cat.sort_values(monto_col, ascending=False)

            fig = px.pie(
                grp_cat,
                values=monto_col,
                names="categoria",
                hole=0.45,
                color_discrete_sequence=ASSET_COLORS,
            )
            fig.update_traces(textinfo="label+percent", textfont_size=11)
            fig.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        section_title("Evolución mensual")
        df_filt["mes"] = df_filt["fecha"].dt.to_period("M").astype(str)
        grp_mes = df_filt.groupby("mes")[monto_col].sum().reset_index()

        fig2 = px.bar(
            grp_mes, x="mes", y=monto_col,
            labels={"mes": "", monto_col: "CLP"},
            color_discrete_sequence=["#4e79a7"],
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccd6f6",
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#2d3250"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Top categorías ────────────────────────────────────
    if "categoria" in df_filt.columns:
        section_title("Resumen por categoría")
        grp2 = df_filt.groupby("categoria")[monto_col].agg(["sum", "count", "mean"]).reset_index()
        grp2.columns = ["Categoría", "Total", "N° Ops", "Promedio"]
        grp2 = grp2.sort_values("Total", ascending=False)
        grp2["Total"]   = grp2["Total"].apply(fmt_clp)
        grp2["Promedio"] = grp2["Promedio"].apply(fmt_clp)
        st.dataframe(grp2, hide_index=True, use_container_width=True)

    # ── Detalle ───────────────────────────────────────────
    st.divider()
    section_title("Detalle de transacciones")

    show_cols = [c for c in ["fecha", "descripcion", "categoria", monto_col, "moneda", "fuente"] if c in df_filt.columns]
    tbl = df_filt[show_cols].copy().sort_values("fecha", ascending=False)
    if "fecha" in tbl.columns:
        tbl["fecha"] = tbl["fecha"].dt.strftime("%Y-%m-%d")
    if monto_col in tbl.columns:
        tbl[monto_col] = tbl[monto_col].apply(fmt_clp)
    tbl.columns = [c.replace("_", " ").title() for c in tbl.columns]
    st.dataframe(tbl, hide_index=True, use_container_width=True)
