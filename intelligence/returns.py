# ============================================================
# RETURNS CALCULATOR — TODAS las métricas de rentabilidad
#
# Métricas implementadas:
#
#  A. TWR (Time-Weighted Return)    — método Racional, excluye timing
#  B. MWR (Money-Weighted / XIRR)   — IRR anualizada con flujos reales
#  C. Retorno simple                — (V_fin - V_ini - flujos) / V_ini
#  D. Retorno cartera actual        — (V - costo_base) / costo_base
#  E. Retorno anualizado            — TWR^(365/días)
#  F. TWR desde inicio (compuesto)  — si se entrega TWR_pre
#
# Uso:
#   from intelligence.returns import compute_all_returns
#   r = compute_all_returns()
#   print(r["twr_pct"], r["mwr_pct"], r["retorno_cartera_pct"], ...)
# ============================================================

import sys, warnings
from datetime import date, datetime, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
import numpy as np

from database.supabase_client import get_client
from cartera_base import ACCIONES_CL, STOCKS_INTL, CRYPTO, SNAPSHOT_DATE
from intelligence.twr_calculator import compute_twr

USD_CLP = 901.76


# ── A. Retorno de cartera actual (snapshot vs hoy) ──────────
def retorno_cartera_actual() -> dict:
    """
    Retorno simple basado en posiciones actuales:
    (valor - costo) / costo
    donde costo = cantidad × precio_compra (snapshot)
    """
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    for c in ["cantidad", "precio_compra", "precio_actual"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["valor_usd"] = df["cantidad"] * df["precio_actual"]
    df["costo_usd"] = df["cantidad"] * df["precio_compra"]
    df["valor_clp"] = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP, axis=1
    )
    df["costo_clp"] = df.apply(
        lambda r: r["costo_usd"] if r.get("moneda") == "CLP" else r["costo_usd"] * USD_CLP, axis=1
    )

    valor = df["valor_clp"].sum()
    costo = df["costo_clp"].sum()
    ganancia = valor - costo
    retorno = (ganancia / costo * 100) if costo else 0
    return {
        "valor": valor,
        "costo": costo,
        "ganancia": ganancia,
        "retorno_pct": retorno,
    }


# ── B. MWR / XIRR — IRR anualizada con flujos irregulares ───
def xirr(cash_flows: list, dates: list, guess: float = 0.1) -> float:
    """
    XIRR (TIR con fechas irregulares). Newton-Raphson.
    cash_flows: lista de flujos (negativo = outflow/depósito, positivo = inflow/retiro/valor)
    dates: lista de fechas (datetime.date o str ISO)
    Retorna tasa anualizada (decimal).
    """
    if not cash_flows or len(cash_flows) != len(dates):
        return None
    if all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
        return None  # XIRR requiere signos mixtos

    days = [(pd.Timestamp(d) - pd.Timestamp(dates[0])).days for d in dates]

    def npv(r):
        return sum(cf / (1 + r) ** (d / 365.0) for cf, d in zip(cash_flows, days))

    def dnpv(r):
        return sum(-cf * d / 365.0 / (1 + r) ** (d / 365.0 + 1) for cf, d in zip(cash_flows, days))

    r = guess
    for _ in range(100):
        try:
            f = npv(r)
            df = dnpv(r)
            if abs(df) < 1e-12:
                break
            r_new = r - f / df
            if abs(r_new - r) < 1e-7:
                return r_new
            r = max(r_new, -0.9999)  # evitar < -100%
        except (ZeroDivisionError, OverflowError):
            return None
    return r if -0.99 < r < 100 else None


def mwr_portfolio(snapshot_date: str = SNAPSHOT_DATE,
                  end_date: str = None,
                  valor_inicial: float = None,
                  valor_final: float = None,
                  flujo_series: pd.Series = None) -> float:
    """
    MWR/XIRR del portafolio entre snapshot y hoy.
    Si se entregan valor_inicial/final/flujo_series los usa,
    sino los calcula via compute_twr.
    """
    if valor_inicial is None or valor_final is None or flujo_series is None:
        twr_data = compute_twr(snapshot_date, end_date, verbose=False)
        if not twr_data:
            return None
        valor_inicial = twr_data["valor_inicial"]
        valor_final   = twr_data["valor_final"]
        flujo_series  = twr_data["flujo"]

    # Construir cash flows: [-V_inicial, -F_1 (depósito), +F_2 (retiro), ..., +V_final]
    cash_flows = [-valor_inicial]
    fechas = [pd.Timestamp(snapshot_date)]

    for fecha, monto in flujo_series.items():
        if abs(monto) > 1:
            cash_flows.append(-monto)  # depósito = outflow del inversor
            fechas.append(fecha)

    cash_flows.append(valor_final)
    fechas.append(pd.Timestamp(end_date) if end_date else pd.Timestamp(date.today()))

    return xirr(cash_flows, fechas)


# ── F. Composición con TWR pre-snapshot ──────────────────────
def twr_compuesto(twr_pre_pct: float, twr_post_pct: float) -> float:
    """(1 + pre%) × (1 + post%) - 1, ambos en %."""
    return ((1 + twr_pre_pct/100) * (1 + twr_post_pct/100) - 1) * 100


# ── ORQUESTADOR — TODAS LAS MÉTRICAS ─────────────────────────
def compute_all_returns(snapshot_date: str = SNAPSHOT_DATE,
                        end_date: str = None,
                        twr_pre_snapshot_pct: float = None) -> dict:
    """
    Calcula TODAS las métricas y las retorna en un dict.
    """
    if end_date is None:
        end_date = date.today().isoformat()

    print(f"📊 Calculando rentabilidad: {snapshot_date} → {end_date}")

    # A. Cartera actual
    print("  ▶ Retorno cartera actual…")
    cart = retorno_cartera_actual()

    # B+C+E. TWR del período (incluye valor inicial/final, flujos)
    print("  ▶ TWR período…")
    twr_data = compute_twr(snapshot_date, end_date, verbose=False)
    if not twr_data:
        return None

    valor_ini = twr_data["valor_inicial"]
    valor_fin = twr_data["valor_final"]
    flujo_total = twr_data["flujos_netos"]
    ganancia_periodo = valor_fin - valor_ini - flujo_total

    # Retorno simple del período (V_fin - V_ini - flujos) / V_ini
    retorno_simple = (ganancia_periodo / valor_ini * 100) if valor_ini else 0

    # B. MWR / XIRR
    print("  ▶ MWR (XIRR anualizado)…")
    mwr = mwr_portfolio(snapshot_date, end_date,
                        valor_ini, valor_fin, twr_data["flujo"])
    mwr_pct = (mwr * 100) if mwr is not None else None

    # E. TWR anualizado
    dias = twr_data["dias"]
    twr_decimal = twr_data["twr_acum"]
    if dias > 0:
        twr_anualizado_pct = ((1 + twr_decimal) ** (365.25 / dias) - 1) * 100
    else:
        twr_anualizado_pct = None

    # F. TWR compuesto con pre-snapshot
    twr_desde_inicio_pct = None
    if twr_pre_snapshot_pct is not None:
        twr_desde_inicio_pct = twr_compuesto(twr_pre_snapshot_pct, twr_data["twr_pct"])

    return {
        "snapshot_date":          snapshot_date,
        "end_date":                end_date,
        "dias":                    dias,

        # Cartera actual
        "valor_actual":            cart["valor"],
        "costo_base_actual":       cart["costo"],
        "ganancia_cartera":        cart["ganancia"],
        "retorno_cartera_pct":     cart["retorno_pct"],

        # Período
        "valor_inicial":           valor_ini,
        "valor_final":             valor_fin,
        "flujos_netos":            flujo_total,
        "ganancia_periodo":        ganancia_periodo,

        # Métricas
        "twr_pct":                 twr_data["twr_pct"],
        "twr_anualizado_pct":      twr_anualizado_pct,
        "retorno_simple_pct":      retorno_simple,
        "mwr_pct":                 mwr_pct,

        # Compuesto
        "twr_pre_snapshot_pct":    twr_pre_snapshot_pct,
        "twr_desde_inicio_pct":    twr_desde_inicio_pct,
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=SNAPSHOT_DATE)
    p.add_argument("--end", default=None)
    p.add_argument("--twr-pre", type=float, default=None,
                   help="TWR previo en %% (ej 46 para 46%%)")
    args = p.parse_args()

    print("=" * 60)
    print("📊 RETURNS — Todas las métricas de rentabilidad")
    print("=" * 60)

    r = compute_all_returns(args.start, args.end, args.twr_pre)
    if not r:
        return

    print(f"\n📅 Período: {r['snapshot_date']} → {r['end_date']} ({r['dias']} días)")
    print(f"\n💰 Cartera actual:")
    print(f"   Valor:          ${r['valor_actual']:>15,.0f} CLP")
    print(f"   Costo base:     ${r['costo_base_actual']:>15,.0f} CLP")
    print(f"   Ganancia:       ${r['ganancia_cartera']:>15,.0f} CLP")
    print(f"   ▶ Retorno:                {r['retorno_cartera_pct']:>7.2f}% (snapshot vs hoy, sin TWR)")

    print(f"\n📈 Métricas del período:")
    print(f"   Valor inicial:  ${r['valor_inicial']:>15,.0f} CLP")
    print(f"   Valor final:    ${r['valor_final']:>15,.0f} CLP")
    print(f"   Flujos netos:   ${r['flujos_netos']:>15,.0f} CLP (lo que metiste/sacaste)")
    print(f"   Ganancia $$:    ${r['ganancia_periodo']:>15,.0f} CLP")
    print(f"")
    print(f"   ▶ Retorno simple:         {r['retorno_simple_pct']:>7.2f}% (no anualizado)")
    print(f"   ▶ TWR del período:        {r['twr_pct']:>7.2f}% (método Racional)")
    if r['twr_anualizado_pct'] is not None:
        print(f"   ▶ TWR anualizado:         {r['twr_anualizado_pct']:>7.2f}% (anualizado)")
    if r['mwr_pct'] is not None:
        print(f"   ▶ MWR (XIRR):             {r['mwr_pct']:>7.2f}% (anualizado con flujos)")

    if r['twr_desde_inicio_pct'] is not None:
        print(f"\n🎯 Composición con histórico Racional:")
        print(f"   TWR pre-snapshot:         {r['twr_pre_snapshot_pct']:>7.2f}%")
        print(f"   TWR período (calc):       {r['twr_pct']:>7.2f}%")
        print(f"   ▶ TWR DESDE INICIO:       {r['twr_desde_inicio_pct']:>7.2f}%")

    print("=" * 60)


if __name__ == "__main__":
    main()
