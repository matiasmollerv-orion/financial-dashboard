# ============================================================
# VISTA: GASTOS (SANTANDER) — 2 niveles de categoría
# ============================================================

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils import fmt_clp, section_title, load_gastos, ASSET_COLORS
from dashboard.categorias import categorizar_df

# Paleta para subcategorías
SUBCAT_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

TOP_LEVEL_COLORS = {
    "Fixed Costs": "#4e79a7",
    "Guilt Free":  "#f28e2b",
    "Investments": "#59a14f",
}


def render():
    st.title("💳 Gastos")

    df_raw = load_gastos()

    if df_raw.empty:
        st.info("📂 **No hay gastos cargados aún.**")
        with st.expander("¿Cómo cargar los gastos de Santander?"):
            st.markdown("""
            **Ejecuta en tu terminal:**
            ```bash
            cd ~/Documents/Claude/FinancialDashboard
            source venv/bin/activate
            python load_santander.py
            ```
            """)
        return

    # ── Enriquecer con categorías de 2 niveles ────────────
    df = categorizar_df(df_raw.copy())
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")

    # Excluir Investments y Pago TC del análisis de gastos
    # (Pago TC son los pagos mensuales al banco, no gastos reales)
    EXCLUIR = ["Investments"]
    EXCLUIR_SUBS = ["Pago TC"]

    df_gastos = df[
        ~df["top_level"].isin(EXCLUIR) &
        ~df["subcategoria"].isin(EXCLUIR_SUBS)
    ].copy()

    # ── FILTROS ───────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        años = sorted(df_gastos["fecha"].dt.year.unique(), reverse=True)
        año_sel = st.selectbox("Año", ["Todos"] + [str(a) for a in años])
    with col_f2:
        meses_map = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                     7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
        meses_disp = ["Todos"] + [meses_map[m] for m in sorted(df_gastos["fecha"].dt.month.unique())]
        mes_sel = st.selectbox("Mes", meses_disp)
    with col_f3:
        top_levels = ["Todos"] + sorted(df_gastos["top_level"].dropna().unique().tolist())
        top_sel = st.selectbox("Nivel principal", top_levels)
    with col_f4:
        subcats_disp = ["Todas"] + sorted(df_gastos["subcategoria"].dropna().unique().tolist())
        sub_sel = st.selectbox("Subcategoría", subcats_disp)

    df_f = df_gastos.copy()
    if año_sel != "Todos":
        df_f = df_f[df_f["fecha"].dt.year == int(año_sel)]
    if mes_sel != "Todos":
        mes_num = {v: k for k, v in meses_map.items()}[mes_sel]
        df_f = df_f[df_f["fecha"].dt.month == mes_num]
    if top_sel != "Todos":
        df_f = df_f[df_f["top_level"] == top_sel]
    if sub_sel != "Todas":
        df_f = df_f[df_f["subcategoria"] == sub_sel]

    if df_f.empty:
        st.warning("Sin gastos para el período seleccionado.")
        return

    total  = df_f["monto"].sum()
    n_ops  = len(df_f)
    prom   = total / n_ops if n_ops else 0

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total gastos", fmt_clp(total))
    with c2: st.metric("N° operaciones", str(n_ops))
    with c3: st.metric("Promedio por operación", fmt_clp(prom))

    st.divider()

    # ── GRÁFICOS: FILA 1 ──────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        section_title("Por nivel principal")
        grp_top = (df_f.groupby("top_level")["monto"].sum()
                   .reset_index().sort_values("monto", ascending=False))
        grp_top["pct"] = grp_top["monto"] / grp_top["monto"].sum() * 100
        grp_top["label"] = grp_top.apply(
            lambda r: f"{r['top_level']}<br>{fmt_clp(r['monto'])} ({r['pct']:.1f}%)", axis=1
        )
        fig1 = go.Figure(go.Pie(
            labels=grp_top["top_level"],
            values=grp_top["monto"],
            hole=0.48,
            textinfo="label+percent",
            textfont_size=11,
            marker=dict(colors=[TOP_LEVEL_COLORS.get(t, "#bab0ac") for t in grp_top["top_level"]]),
            hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
            customdata=grp_top["monto"].apply(fmt_clp),
        ))
        fig1.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=10, r=10),
            height=290,
            annotations=[dict(
                text=f"<b>{fmt_clp(total)}</b>",
                x=0.5, y=0.5, font_size=12, showarrow=False, font_color="#ccd6f6"
            )],
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_right:
        section_title("Por subcategoría")
        grp_sub = (df_f.groupby("subcategoria")["monto"].sum()
                   .reset_index().sort_values("monto", ascending=False).head(15))
        grp_sub["pct"] = grp_sub["monto"] / total * 100
        grp_sub["monto_fmt"] = grp_sub["monto"].apply(fmt_clp)
        fig2 = px.bar(
            grp_sub.sort_values("monto"),
            x="monto", y="subcategoria",
            orientation="h",
            color="subcategoria",
            color_discrete_sequence=SUBCAT_COLORS,
            custom_data=["pct", "monto_fmt"],
            labels={"monto": "", "subcategoria": ""},
        )
        fig2.update_traces(
            hovertemplate="<b>%{y}</b><br>%{customdata[1]}<br>%{customdata[0]:.1f}% del total<extra></extra>",
            texttemplate="%{customdata[1]}",
            textposition="outside",
        )
        fig2.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccd6f6",
            margin=dict(t=10, b=10, l=5, r=80),
            height=290,
            xaxis=dict(
                tickformat=",.0f",
                gridcolor="#2d3250",
                tickprefix="$",
            ),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── GRÁFICO: EVOLUCIÓN MENSUAL APILADA ────────────────
    st.divider()
    section_title("Evolución mensual por subcategoría")

    df_f["mes"] = df_f["fecha"].dt.to_period("M").astype(str)

    # Pivot para stacked bar
    grp_mes_sub = (df_f.groupby(["mes", "subcategoria"])["monto"]
                   .sum().reset_index())
    total_por_mes = df_f.groupby("mes")["monto"].sum().rename("total_mes")
    grp_mes_sub = grp_mes_sub.merge(total_por_mes, on="mes")
    grp_mes_sub["pct_mes"] = grp_mes_sub["monto"] / grp_mes_sub["total_mes"] * 100
    grp_mes_sub["monto_fmt"] = grp_mes_sub["monto"].apply(fmt_clp)
    grp_mes_sub["total_mes_fmt"] = grp_mes_sub["total_mes"].apply(fmt_clp)

    # Ordenar subcategorías por total descendente para colores consistentes
    orden_subs = (grp_mes_sub.groupby("subcategoria")["monto"]
                  .sum().sort_values(ascending=False).index.tolist())

    fig3 = px.bar(
        grp_mes_sub,
        x="mes",
        y="monto",
        color="subcategoria",
        barmode="stack",
        category_orders={"subcategoria": orden_subs},
        color_discrete_sequence=SUBCAT_COLORS,
        custom_data=["subcategoria", "pct_mes", "total_mes_fmt", "monto_fmt"],
        labels={"mes": "", "monto": "CLP", "subcategoria": ""},
    )
    fig3.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            "%{customdata[0]}<br>"
            "Monto: %{customdata[3]}<br>"
            "%{customdata[1]:.1f}% del período<br>"
            "Total mes: %{customdata[2]}"
            "<extra></extra>"
        )
    )
    # Formato del eje Y en CLP
    max_val = grp_mes_sub.groupby("mes")["monto"].sum().max()
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccd6f6",
        margin=dict(t=10, b=10, l=10, r=10),
        height=400,
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(
            gridcolor="#2d3250",
            tickformat=",.0f",
            tickprefix="$",
        ),
        legend=dict(
            orientation="h",
            y=-0.25,
            font=dict(size=10),
        ),
    )
    st.plotly_chart(fig3, use_container_width=True)

    # ── TABLA: RESUMEN POR SUBCATEGORÍA ───────────────────
    st.divider()
    section_title("Resumen por categoría")

    grp_tbl = (df_f.groupby(["top_level", "subcategoria"])["monto"]
               .agg(Total="sum", Ops="count", Promedio="mean")
               .reset_index()
               .sort_values("Total", ascending=False))
    grp_tbl["% Total"] = (grp_tbl["Total"] / total * 100).round(1).astype(str) + "%"
    grp_tbl["Total"]    = grp_tbl["Total"].apply(fmt_clp)
    grp_tbl["Promedio"] = grp_tbl["Promedio"].apply(fmt_clp)
    grp_tbl.columns = ["Nivel", "Subcategoría", "Total", "N° Ops", "Promedio", "% Total"]
    st.dataframe(grp_tbl, hide_index=True, use_container_width=True)

    # ── DETALLE ───────────────────────────────────────────
    st.divider()
    section_title("Detalle de transacciones")

    show_cols = [c for c in ["fecha", "descripcion", "top_level", "subcategoria", "monto", "moneda"] if c in df_f.columns]
    tbl = df_f[show_cols].copy().sort_values("fecha", ascending=False)
    if "fecha" in tbl.columns:
        tbl["fecha"] = tbl["fecha"].dt.strftime("%Y-%m-%d")
    if "monto" in tbl.columns:
        tbl["monto"] = tbl["monto"].apply(fmt_clp)
    tbl.columns = [c.replace("_", " ").title() for c in tbl.columns]
    st.dataframe(tbl, hide_index=True, use_container_width=True)

    # ── EXPLORAR CATEGORÍA ────────────────────────────────
    st.divider()
    section_title("🔍 Explorar una categoría")

    # Construir opciones de categorías disponibles en el filtro actual
    cats_grp = (df_f.groupby(["top_level", "subcategoria"])["monto"]
                .sum().reset_index().sort_values("monto", ascending=False))
    cat_opciones = cats_grp.apply(
        lambda r: f"{r['top_level']} › {r['subcategoria']}  ({fmt_clp(r['monto'])})", axis=1
    ).tolist()

    cat_sel_raw = st.selectbox(
        "Selecciona una categoría para ver el detalle:",
        ["— Seleccionar —"] + cat_opciones,
        key="cat_drill",
    )

    if cat_sel_raw != "— Seleccionar —":
        # Extraer top_level y subcategoria (antes del primer "  (")
        cat_str = cat_sel_raw.split("  (")[0]
        top_drll, sub_drll = cat_str.split(" › ", 1)
        df_cat = df_f[(df_f["top_level"] == top_drll) & (df_f["subcategoria"] == sub_drll)].copy()

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Total", fmt_clp(df_cat["monto"].sum()))
        with c2: st.metric("N° operaciones", len(df_cat))
        with c3: st.metric("Ticket promedio", fmt_clp(df_cat["monto"].mean()))

        col_l, col_r = st.columns(2)

        with col_l:
            # Tendencia mensual
            df_cat["_mes"] = df_cat["fecha"].dt.to_period("M").astype(str)
            trend = df_cat.groupby("_mes")["monto"].sum().reset_index()
            trend["monto_fmt"] = trend["monto"].apply(fmt_clp)
            fig_t = px.bar(
                trend, x="_mes", y="monto",
                custom_data=["monto_fmt"],
                labels={"_mes": "", "monto": ""},
                color_discrete_sequence=["#4e79a7"],
            )
            fig_t.update_traces(
                hovertemplate="<b>%{x}</b><br>%{customdata[0]}<extra></extra>",
            )
            fig_t.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccd6f6", height=240,
                margin=dict(t=5, b=5, l=5, r=5),
                xaxis=dict(showgrid=False, tickangle=-45),
                yaxis=dict(gridcolor="#2d3250"),
            )
            st.plotly_chart(fig_t, use_container_width=True)

        with col_r:
            # Top merchants / descripciones
            top_merch = (df_cat.groupby("descripcion")["monto"]
                         .agg(Total="sum", Veces="count")
                         .reset_index()
                         .sort_values("Total", ascending=False)
                         .head(10))
            top_merch["Total"] = top_merch["Total"].apply(fmt_clp)
            top_merch.columns = ["Descripción", "Total", "Veces"]
            st.dataframe(top_merch, hide_index=True, use_container_width=True, height=240)

        # Transacciones completas
        with st.expander(f"Ver todas las transacciones ({len(df_cat)})"):
            tbl_cat = df_cat[["fecha", "descripcion", "monto"]].sort_values("fecha", ascending=False).copy()
            tbl_cat["fecha"] = tbl_cat["fecha"].dt.strftime("%Y-%m-%d")
            tbl_cat["monto"] = tbl_cat["monto"].apply(fmt_clp)
            tbl_cat.columns = ["Fecha", "Descripción", "Monto"]
            st.dataframe(tbl_cat, hide_index=True, use_container_width=True)

    # ── ALERTAS ───────────────────────────────────────────
    st.divider()
    section_title("🚨 Alertas de gastos")

    alertas = []

    # 1. Posibles duplicados: mismo (descripcion, monto) en la misma semana
    if len(df_f) > 0:
        df_dup = df_f.copy()
        df_dup["_semana"] = df_dup["fecha"].dt.to_period("W").astype(str)
        dups = (df_dup.groupby(["_semana", "descripcion", "monto"])
                .filter(lambda g: len(g) > 1)
                .sort_values(["descripcion", "fecha"]))
        if not dups.empty:
            tbl_dup = dups[["fecha", "descripcion", "subcategoria", "monto"]].copy()
            tbl_dup["fecha"] = tbl_dup["fecha"].dt.strftime("%Y-%m-%d")
            tbl_dup["monto"] = tbl_dup["monto"].apply(fmt_clp)
            tbl_dup.columns = ["Fecha", "Descripción", "Subcategoría", "Monto"]
            alertas.append(("⚠️ Posibles cobros duplicados", tbl_dup,
                            "Misma descripción y monto en la misma semana"))

    # 2. Outliers: monto > Q3 + 3×IQR por subcategoría (con mínimo 4 transacciones)
    df_out_list = []
    for sub, grp in df_f.groupby("subcategoria"):
        if len(grp) < 4:
            continue
        q1 = grp["monto"].quantile(0.25)
        q3 = grp["monto"].quantile(0.75)
        iqr = q3 - q1
        umbral = q3 + 3 * iqr
        anom = grp[grp["monto"] > umbral]
        if not anom.empty:
            df_out_list.append(anom)
    if df_out_list:
        df_out = pd.concat(df_out_list).sort_values("monto", ascending=False)
        tbl_out = df_out[["fecha", "descripcion", "subcategoria", "monto"]].copy()
        tbl_out["fecha"] = tbl_out["fecha"].dt.strftime("%Y-%m-%d")
        tbl_out["monto"] = tbl_out["monto"].apply(fmt_clp)
        tbl_out.columns = ["Fecha", "Descripción", "Subcategoría", "Monto"]
        alertas.append(("💸 Gastos atípicos (outliers por categoría)", tbl_out,
                        "Monto muy superior al rango habitual de esa categoría"))

    # 3. Sin categorizar con monto significativo (>$30.000)
    df_sin = df_f[(df_f["top_level"] == "Sin Categorizar") & (df_f["monto"] > 30_000)]
    if not df_sin.empty:
        tbl_sin = df_sin[["fecha", "descripcion", "monto"]].sort_values("monto", ascending=False).copy()
        tbl_sin["fecha"] = tbl_sin["fecha"].dt.strftime("%Y-%m-%d")
        tbl_sin["monto"] = tbl_sin["monto"].apply(fmt_clp)
        tbl_sin.columns = ["Fecha", "Descripción", "Monto"]
        alertas.append(("❓ Sin categorizar con monto significativo", tbl_sin,
                        "Transacciones >$30.000 sin categoría asignada"))

    # 4. Cobros en USD dentro de tarjeta nacional (pueden ser cargos inesperados)
    if "moneda" in df_f.columns:
        df_usd = df_f[df_f["moneda"] == "USD"].sort_values("monto", ascending=False)
        if not df_usd.empty:
            tbl_usd = df_usd[["fecha", "descripcion", "monto", "moneda"]].copy()
            tbl_usd["fecha"] = tbl_usd["fecha"].dt.strftime("%Y-%m-%d")
            tbl_usd["monto"] = tbl_usd["monto"].apply(lambda x: f"USD {x:,.2f}")
            tbl_usd.columns = ["Fecha", "Descripción", "Monto USD", "Moneda"]
            alertas.append(("🌐 Cargos en moneda extranjera (USD)", tbl_usd,
                            "Transacciones facturadas en USD"))

    if not alertas:
        st.success("✅ Sin alertas en el período seleccionado.")
    else:
        for titulo, tbl_alerta, desc in alertas:
            with st.expander(f"{titulo} — {len(tbl_alerta)} caso(s)"):
                st.caption(desc)
                st.dataframe(tbl_alerta, hide_index=True, use_container_width=True)
