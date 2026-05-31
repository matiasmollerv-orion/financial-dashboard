# ============================================================
# VISTA: CUENTA CORRIENTE SANTANDER
# Categorización paralela a Gastos: top_level + subcategoria.
# ============================================================

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_clp_safe, metric_safe, section_title, load_cuenta,
)
from dashboard.categorias_cuenta import categorizar_df


# Mismos colores que gastos.py
TOP_LEVEL_COLORS = {
    "Fixed Costs":     "#4e79a7",
    "Guilt Free":      "#f28e2b",
    "Investments":     "#59a14f",
    "Impuestos":       "#e15759",
    "Familia":         "#76b7b2",
    "Ingresos":        "#1f9d55",
    "Excluir":         "#bab0ac",
    "Sin Categorizar": "#7f7f7f",
}

CONTA_COLORS = {
    "gasto":    "#e15759",
    "ingreso":  "#59a14f",
    "excluir":  "#bab0ac",
    "neutro":   "#76b7b2",
}


def render():
    st.title("🏦 Cuenta Corriente")

    with st.sidebar:
        if st.button("🔄 Recargar cuenta", help="Limpia caché y recarga desde Supabase"):
            load_cuenta.clear()
            st.rerun()

    df = load_cuenta()
    if df.empty:
        st.info("📂 No hay movimientos de cuenta corriente cargados.")
        return

    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[df["fecha"].notna()]
    df = categorizar_df(df)

    st.caption(
        f"📦 {len(df):,} movimientos · "
        f"{df['fecha'].min().strftime('%Y-%m-%d')} → {df['fecha'].max().strftime('%Y-%m-%d')}"
    )

    # ── Filtros ────────────────────────────────────────────
    df["año"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    años = sorted(df["año"].unique(), reverse=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        año_sel = st.selectbox("Año", ["Todos"] + [str(a) for a in años])
    with c2:
        meses_disp = ["Todos"] + sorted(df["mes"].unique(), reverse=True)
        mes_sel = st.selectbox("Mes", meses_disp)
    with c3:
        tops = ["Todos"] + sorted(df["cc_top_level"].unique())
        top_sel = st.selectbox("Categoría", tops)
    with c4:
        contas = ["Todos"] + sorted(df["cc_contabilidad"].unique())
        conta_sel = st.selectbox("Tipo contable", contas)

    df_f = df.copy()
    if año_sel != "Todos":
        df_f = df_f[df_f["año"] == int(año_sel)]
    if mes_sel != "Todos":
        df_f = df_f[df_f["mes"] == mes_sel]
    if top_sel != "Todos":
        df_f = df_f[df_f["cc_top_level"] == top_sel]
    if conta_sel != "Todos":
        df_f = df_f[df_f["cc_contabilidad"] == conta_sel]

    if df_f.empty:
        st.info("Sin movimientos con esos filtros.")
        return

    # ── KPIs por contabilidad ──────────────────────────────
    by_conta = df_f.groupby("cc_contabilidad")["monto"].sum().to_dict()
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_safe("💸 Gastos reales", fmt_clp_safe(by_conta.get("gasto", 0)),
                    help="Movimientos clasificados como gasto real (excluye Pago TC e Inversiones).")
    with k2:
        metric_safe("💰 Ingresos", fmt_clp_safe(by_conta.get("ingreso", 0)),
                    help="Sueldos, ventas, devoluciones.")
    with k3:
        metric_safe("🚫 Excluidos (doble conteo)", fmt_clp_safe(by_conta.get("excluir", 0)),
                    help="Pago TC, inversiones, traspasos propios — YA están en otra fuente.")
    with k4:
        metric_safe("⚪ Neutros (familia)", fmt_clp_safe(by_conta.get("neutro", 0)),
                    help="Familia / pareja / amigos: informativo.")

    # ── TORTA por top_level ────────────────────────────────
    section_title("📊 Distribución por categoría principal")
    grp_tl = df_f.groupby("cc_top_level")["monto"].sum().reset_index().sort_values("monto", ascending=False)
    grp_tl["monto_fmt"] = grp_tl["monto"].apply(fmt_clp)
    fig_tl = px.pie(
        grp_tl, values="monto", names="cc_top_level", hole=0.45,
        color="cc_top_level", color_discrete_map=TOP_LEVEL_COLORS,
    )
    fig_tl.update_traces(
        textposition="outside", textinfo="label+percent",
        customdata=grp_tl[["monto_fmt"]].values,
        hovertemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(fig_tl, use_container_width=True)

    # ── BARRAS por subcategoría dentro de cada top_level ───
    section_title("🔎 Subcategorías")
    grp_sub = (df_f.groupby(["cc_top_level", "cc_subcategoria"])["monto"]
                  .sum().reset_index().sort_values("monto", ascending=False))
    grp_sub["monto_fmt"] = grp_sub["monto"].apply(fmt_clp)
    fig_sub = px.bar(
        grp_sub.sort_values("monto"),
        x="monto", y="cc_subcategoria", orientation="h",
        color="cc_top_level", color_discrete_map=TOP_LEVEL_COLORS,
        custom_data=["cc_top_level", "monto_fmt"],
        labels={"monto":"CLP", "cc_subcategoria":""},
    )
    fig_sub.update_traces(
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"
    )
    fig_sub.update_layout(height=max(300, len(grp_sub) * 22))
    st.plotly_chart(fig_sub, use_container_width=True)

    # ── EVOLUCIÓN MENSUAL por contabilidad (gasto/ingreso/excluir/neutro) ──
    section_title("📅 Evolución mensual por tipo contable")
    grp_m = (df_f.groupby(["mes", "cc_contabilidad"])["monto"]
                .sum().reset_index())
    grp_m["monto_fmt"] = grp_m["monto"].apply(fmt_clp)
    fig_m = px.bar(
        grp_m.sort_values("mes"),
        x="mes", y="monto", color="cc_contabilidad",
        color_discrete_map=CONTA_COLORS,
        custom_data=["monto_fmt", "cc_contabilidad"],
    )
    fig_m.update_traces(
        hovertemplate="<b>%{x}</b><br>%{customdata[1]}: %{customdata[0]}<extra></extra>"
    )
    fig_m.update_layout(barmode="group", xaxis_title="", yaxis_title="CLP")
    st.plotly_chart(fig_m, use_container_width=True)

    # ── TABLA DETALLE ──────────────────────────────────────
    section_title(f"📋 Detalle — {len(df_f)} movimientos")
    df_show = df_f.sort_values("fecha", ascending=False).copy()
    df_show["fecha"] = df_show["fecha"].dt.strftime("%Y-%m-%d")
    df_show["monto_fmt"] = df_show["monto"].apply(fmt_clp_safe)
    cols = ["fecha", "descripcion", "cc_top_level", "cc_subcategoria", "cc_contabilidad", "monto_fmt"]
    st.dataframe(
        df_show[cols].rename(columns={
            "fecha":"Fecha", "descripcion":"Descripción",
            "cc_top_level":"Categoría", "cc_subcategoria":"Subcategoría",
            "cc_contabilidad":"Tipo", "monto_fmt":"Monto",
        }),
        hide_index=True, use_container_width=True, height=500,
    )

    # ── SIN CATEGORIZAR (drill-down para mejorar reglas) ───
    sin_cat = df_f[df_f["cc_top_level"] == "Sin Categorizar"]
    if not sin_cat.empty:
        with st.expander(f"🔍 Sin categorizar ({len(sin_cat)} movs, ${sin_cat['monto'].sum():,.0f}) — agrupados por descripción"):
            grp_sc = (sin_cat.groupby("descripcion")
                            .agg(n=("monto", "size"), total=("monto", "sum"))
                            .reset_index().sort_values("total", ascending=False))
            grp_sc["total_fmt"] = grp_sc["total"].apply(fmt_clp)
            st.dataframe(grp_sc[["descripcion","n","total_fmt"]].rename(columns={
                "descripcion":"Descripción","n":"N° veces","total_fmt":"Total"
            }), hide_index=True, use_container_width=True)
