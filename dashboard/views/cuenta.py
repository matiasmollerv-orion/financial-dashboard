# ============================================================
# VISTA: CUENTA CORRIENTE SANTANDER
# Muestra movimientos categorizados (gasto / ingreso / excluido / neutro)
# para evitar doble contar con santander_gastos (TC) y racional (inversiones).
# ============================================================

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.utils import (
    fmt_clp, fmt_clp_safe, metric_safe, section_title, load_cuenta,
)
from dashboard.categorias_cuenta import categorizar_df


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
    df = categorizar_df(df)

    # ── Aviso del bug conocido ─────────────────────────────
    st.caption(
        f"📦 {len(df):,} movimientos · "
        f"{df['fecha'].min().strftime('%Y-%m-%d')} → {df['fecha'].max().strftime('%Y-%m-%d')}"
    )
    if (df["tipo"] == "abono").all():
        st.warning(
            "⚠️ Bug conocido del parser: todos los movimientos están marcados como `abono`. "
            "La categorización por descripción funciona igual (no usa `tipo`), "
            "pero el signo cargo/abono no es confiable. Pendiente arreglar `extractors/santander_pdf.py`."
        )

    # ── Filtros ────────────────────────────────────────────
    df["año"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    años = sorted(df["año"].unique(), reverse=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        año_sel = st.selectbox("Año", ["Todos"] + [str(a) for a in años])
    with c2:
        meses_disp = ["Todos"] + sorted(df["mes"].unique(), reverse=True)
        mes_sel = st.selectbox("Mes", meses_disp)
    with c3:
        contas = ["Todos"] + sorted(df["cc_contabilidad"].unique())
        conta_sel = st.selectbox("Tipo contable", contas)

    df_f = df.copy()
    if año_sel != "Todos":
        df_f = df_f[df_f["año"] == int(año_sel)]
    if mes_sel != "Todos":
        df_f = df_f[df_f["mes"] == mes_sel]
    if conta_sel != "Todos":
        df_f = df_f[df_f["cc_contabilidad"] == conta_sel]

    if df_f.empty:
        st.info("Sin movimientos con esos filtros.")
        return

    # ── KPIs ───────────────────────────────────────────────
    by_conta = df_f.groupby("cc_contabilidad")["monto"].sum().to_dict()
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_safe("💸 Gastos reales", fmt_clp_safe(by_conta.get("gasto", 0)),
                    help="Movimientos clasificados como gasto real (NO incluye pago TC ni inversiones).")
    with k2:
        metric_safe("💰 Ingresos", fmt_clp_safe(by_conta.get("ingreso", 0)),
                    help="Sueldos, devoluciones, ingresos laborales.")
    with k3:
        metric_safe("🚫 Excluidos (doble conteo)", fmt_clp_safe(by_conta.get("excluir", 0)),
                    help="Pago TC, inversiones, traspasos propios — YA están contados en otra fuente.")
    with k4:
        metric_safe("⚪ Neutros", fmt_clp_safe(by_conta.get("neutro", 0)),
                    help="Cambio divisas, transferencias familiares, notas de crédito.")

    # ── Pie por categoría ──────────────────────────────────
    section_title("📊 Distribución por categoría")
    grp = (df_f.groupby(["cc_categoria", "cc_contabilidad"])["monto"]
              .sum().reset_index().sort_values("monto", ascending=False))
    grp["monto_fmt"] = grp["monto"].apply(fmt_clp)
    grp["label"] = grp.apply(
        lambda r: f"{r['cc_categoria']} ({r['cc_contabilidad']})", axis=1
    )
    fig = px.pie(
        grp, values="monto", names="label", hole=0.4,
        color="cc_contabilidad", color_discrete_map=CONTA_COLORS,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="label+percent",
        customdata=grp[["monto_fmt"]].values,
        hovertemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{percent}<extra></extra>",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Barras por mes ─────────────────────────────────────
    section_title("📅 Evolución mensual por tipo contable")
    grp_m = (df_f.groupby(["mes", "cc_contabilidad"])["monto"]
                .sum().reset_index())
    grp_m["monto_fmt"] = grp_m["monto"].apply(fmt_clp)
    fig2 = px.bar(
        grp_m.sort_values("mes"),
        x="mes", y="monto", color="cc_contabilidad",
        color_discrete_map=CONTA_COLORS,
        custom_data=["monto_fmt", "cc_contabilidad"],
    )
    fig2.update_traces(
        hovertemplate="<b>%{x}</b><br>%{customdata[1]}: %{customdata[0]}<extra></extra>"
    )
    fig2.update_layout(barmode="group", xaxis_title="", yaxis_title="CLP")
    st.plotly_chart(fig2, use_container_width=True)

    # ── Tabla detalle ──────────────────────────────────────
    section_title(f"📋 Detalle — {len(df_f)} movimientos")
    df_show = df_f.sort_values("fecha", ascending=False).copy()
    df_show["fecha"] = df_show["fecha"].dt.strftime("%Y-%m-%d")
    df_show["monto_fmt"] = df_show["monto"].apply(fmt_clp_safe)
    cols = ["fecha", "descripcion", "cc_categoria", "cc_contabilidad", "monto_fmt"]
    st.dataframe(
        df_show[cols].rename(columns={
            "fecha": "Fecha", "descripcion": "Descripción",
            "cc_categoria": "Categoría", "cc_contabilidad": "Tipo",
            "monto_fmt": "Monto",
        }),
        hide_index=True, use_container_width=True, height=500,
    )

    # ── Sin categorizar (para mejorar reglas) ──────────────
    sin_cat = df_f[df_f["cc_categoria"] == "Sin categorizar"]
    if not sin_cat.empty:
        with st.expander(f"🔍 Sin categorizar ({len(sin_cat)}) — agrupados por descripción"):
            grp_sc = (sin_cat.groupby("descripcion")
                            .agg(n=("monto", "size"), total=("monto", "sum"))
                            .reset_index().sort_values("total", ascending=False))
            grp_sc["total"] = grp_sc["total"].apply(fmt_clp)
            st.dataframe(grp_sc, hide_index=True, use_container_width=True)
