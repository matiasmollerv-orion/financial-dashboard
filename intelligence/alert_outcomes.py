# ============================================================
# ALERT OUTCOMES v1 — Feedback loop: ¿las alertas funcionan?
#
# Cada alerta guarda "precio" en metricas al momento de crearse.
# Este job (diario) registra el retorno forward a +5, +20 y +60
# días DENTRO del mismo JSON metricas (sin necesidad de DDL):
#
#   metricas.outcome_5d_pct / outcome_20d_pct / outcome_60d_pct
#
# Con --scorecard imprime hit rates por tipo de regla, lo que
# permite recalibrar el sistema con datos propios.
#
# Uso:
#   python -m intelligence.alert_outcomes            # registrar outcomes
#   python -m intelligence.alert_outcomes --scorecard # ver calibración
# ============================================================

import sys, argparse, warnings
from datetime import date, datetime, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import pandas as pd
from database.supabase_client import get_client

# Categorías cuya efectividad queremos medir
SIGNAL_CATS = [
    "oportunidad_dip", "oportunidad_rsi2", "watchlist_entry", "watchlist_tier2",
    "momentum_warning", "insider_buy", "insider_cluster", "smart_money_13f",
    "venta_trailing", "venta_evaluar",
]
# Para estas, un buen outcome es que el precio SUBA después de la alerta
BUY_CATS = {"oportunidad_dip", "oportunidad_rsi2", "watchlist_entry",
            "watchlist_tier2", "insider_buy", "insider_cluster", "smart_money_13f"}
# Para estas, un buen outcome es que el precio BAJE (la advertencia era correcta)
SELL_CATS = {"momentum_warning", "venta_trailing"}

WINDOWS = [5, 20, 60]


def fetch_alerts_pending() -> list:
    """Alertas de señal con precio, de los últimos 70 días, con outcomes incompletos."""
    sb = get_client()
    cutoff = (date.today() - timedelta(days=70)).isoformat()
    rows, page = [], 0
    while True:
        r = (sb.table("portfolio_alerts").select("*")
             .in_("categoria", SIGNAL_CATS)
             .gte("fecha_alerta", cutoff)
             .range(page * 1000, page * 1000 + 999).execute())
        rows.extend(r.data)
        if len(r.data) < 1000:
            break
        page += 1
    out = []
    for a in rows:
        m = a.get("metricas") or {}
        if not isinstance(m, dict) or not m.get("precio"):
            continue
        if all(f"outcome_{w}d_pct" in m for w in WINDOWS):
            continue
        out.append(a)
    return out


NACIONALES = {"BCI", "CENCOSUD", "FALABELLA", "PARAUCO", "COPEC", "CMPC",
              "BSANTANDER", "CHILE", "COLBUN", "IAM", "ENELAM", "QUINENCO",
              "CAP", "SMU", "LTM", "ITAUCL", "ENELCHILE", "ENJOY", "SQM-B"}


def yf_symbol(ticker: str) -> str:
    if ticker in ("BTC", "ETH"):
        return f"{ticker}-USD"
    base = ticker.replace("_STG", "")
    if base in NACIONALES:
        return f"{base}.SN"
    return ticker


def record_outcomes(dry_run: bool = False):
    alerts = fetch_alerts_pending()
    print(f"{len(alerts)} alertas con outcomes pendientes")
    if not alerts:
        return

    tickers = sorted({a["activo"] for a in alerts if a["activo"] not in ("PORTFOLIO", "?")})
    import yfinance as yf
    raw = yf.download([yf_symbol(t) for t in tickers], period="5d", interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    if raw.empty:
        print("Sin precios actuales.")
        return

    def price_now(tk):
        sym = yf_symbol(tk)
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                s = raw[sym]["Close"].dropna()
            else:
                s = raw["Close"].dropna()
            return float(s.iloc[-1]) if len(s) else None
        except Exception:
            return None

    sb = get_client()
    hoy = date.today()
    updated = 0
    for a in alerts:
        m = dict(a.get("metricas") or {})
        p0 = float(m["precio"])
        try:
            f_alerta = datetime.fromisoformat(a["fecha_alerta"].replace("Z", "+00:00")).date()
        except Exception:
            continue
        elapsed = (hoy - f_alerta).days
        p_now = price_now(a["activo"])
        if not p_now or p0 <= 0:
            continue

        changed = False
        for w in WINDOWS:
            key = f"outcome_{w}d_pct"
            if key in m or elapsed < w:
                continue
            m[key] = round((p_now / p0 - 1) * 100, 2)
            m[f"outcome_{w}d_dias_reales"] = elapsed
            changed = True

        if changed and not dry_run:
            try:
                sb.table("portfolio_alerts").update({"metricas": m}).eq("id", a["id"]).execute()
                updated += 1
            except Exception as e:
                print(f"  {a['activo']}: {str(e)[:80]}")
        elif changed:
            updated += 1

    print(f"Outcomes registrados en {updated} alertas" + (" (dry run)" if dry_run else ""))


def scorecard():
    """Hit rate por categoría/regla usando los outcomes acumulados."""
    sb = get_client()
    rows, page = [], 0
    while True:
        r = (sb.table("portfolio_alerts").select("categoria,activo,metricas,fecha_alerta")
             .in_("categoria", SIGNAL_CATS)
             .range(page * 1000, page * 1000 + 999).execute())
        rows.extend(r.data)
        if len(r.data) < 1000:
            break
        page += 1

    data = []
    for a in rows:
        m = a.get("metricas") or {}
        if not isinstance(m, dict):
            continue
        if not any(f"outcome_{w}d_pct" in m for w in WINDOWS):
            continue
        data.append({
            "categoria": a["categoria"],
            "rule": m.get("rule", "-"),
            "o5": m.get("outcome_5d_pct"),
            "o20": m.get("outcome_20d_pct"),
            "o60": m.get("outcome_60d_pct"),
        })
    if not data:
        print("Aún no hay outcomes registrados. El job diario los irá acumulando.")
        return

    df = pd.DataFrame(data)
    print("=" * 76)
    print("SCORECARD — efectividad de alertas (retornos forward desde la alerta)")
    print("=" * 76)
    print(f"{'Categoría':24s} {'Regla':14s} {'N':>4s} {'+5d':>7s} {'+20d':>7s} {'+60d':>7s} {'Hit':>6s}")
    print("-" * 76)
    for (cat, rule), g in df.groupby(["categoria", "rule"]):
        n = len(g)
        m5 = g["o5"].dropna().mean()
        m20 = g["o20"].dropna().mean()
        m60 = g["o60"].dropna().mean()
        # Hit: para señales de compra, % con retorno 20d positivo;
        # para advertencias de venta, % con retorno 20d negativo
        base = g["o20"].dropna()
        if len(base):
            hit = (base > 0).mean() * 100 if cat in BUY_CATS else \
                  (base < 0).mean() * 100 if cat in SELL_CATS else float("nan")
        else:
            hit = float("nan")
        def fmt(x):
            return f"{x:+.1f}%" if pd.notna(x) else "  —  "
        print(f"{cat:24s} {str(rule):14s} {n:>4d} {fmt(m5):>7s} {fmt(m20):>7s} {fmt(m60):>7s} "
              f"{hit:>5.0f}%" if pd.notna(hit) else
              f"{cat:24s} {str(rule):14s} {n:>4d} {fmt(m5):>7s} {fmt(m20):>7s} {fmt(m60):>7s}    — ")
    print("-" * 76)
    print("Hit = % de alertas 'correctas' a 20 días (sube tras compra / baja tras advertencia)")
    print("Usa esto para subir/bajar pesos de reglas en rules.yaml con datos propios.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scorecard", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("ALERT OUTCOMES v1 — Feedback loop")
    print("=" * 60)
    if args.scorecard:
        scorecard()
    else:
        record_outcomes(dry_run=args.dry_run)
    print("=" * 60)


if __name__ == "__main__":
    main()
