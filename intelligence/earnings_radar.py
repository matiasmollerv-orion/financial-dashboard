# ============================================================
# EARNINGS RADAR v1 — Aviso ANTES de earnings, no después
#
# Alerta cuando una posición grande de cartera o un tier1 de la
# watchlist reporta earnings en los próximos N días. La idea:
# decidir ANTES (agregar, cubrir, o no hacer nada conscientemente)
# en vez de enterarse por el gap del día siguiente.
#
# Uso:
#   python -m intelligence.earnings_radar
#   python -m intelligence.earnings_radar --dry-run --days 7
# ============================================================

import sys, argparse, warnings
from datetime import date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import yaml
import pandas as pd
from pathlib import Path

from database.supabase_client import get_client

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"
MIN_POSITION_USD = 1500  # solo posiciones que ameritan atención pre-earnings


def build_universe() -> dict:
    """ticker → valor_usd (0 para watchlist tier1 sin posición)."""
    universe = {}
    try:
        sb = get_client()
        r = sb.table("cartera_actual").select("ticker,mercado,cantidad,precio_actual").execute()
        for row in r.data:
            if row.get("mercado") != "internacional":
                continue
            try:
                val = float(row["cantidad"]) * float(row["precio_actual"])
            except (TypeError, ValueError):
                continue
            if val >= MIN_POSITION_USD:
                universe[row["ticker"]] = val
    except Exception as e:
        print(f"  Warning cartera: {e}")

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl = yaml.safe_load(f)
    for i in wl.get("watchlist", {}).get("tier1", []):
        universe.setdefault(i["ticker"], 0)
    # ETFs no reportan earnings
    etfs_extra = {"VTV", "EWY", "INDA", "ILF", "EWJ", "FTEC", "URNM", "GLDM",
                  "EWZ", "FXI", "ARKK", "SMH", "SOXX", "QQQ", "IWM", "PURR", "VCX"}
    for etf in set(wl.get("etfs_core_no_alert", [])) | etfs_extra:
        universe.pop(etf, None)
    return universe


def next_earnings_date(ticker: str):
    """Próxima fecha de earnings via yfinance. None si no disponible."""
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        # yfinance moderno retorna dict; antiguo DataFrame
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date") or []
            if dates:
                d = dates[0]
                return d if isinstance(d, date) else pd.Timestamp(d).date()
        elif cal is not None and not getattr(cal, "empty", True):
            d = cal.loc["Earnings Date"].iloc[0]
            return pd.Timestamp(d).date()
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=5,
                        help="Avisar si earnings en <= N días (default 5)")
    args = parser.parse_args()

    print("=" * 60)
    print("EARNINGS RADAR v1 — Aviso previo de resultados")
    print("=" * 60)

    universe = build_universe()
    print(f"\n{len(universe)} tickers a chequear (posiciones > USD {MIN_POSITION_USD} + tier1)")

    hoy = date.today()
    alerts = []
    for tk, val in sorted(universe.items(), key=lambda x: -x[1]):
        d = next_earnings_date(tk)
        if not d:
            continue
        dias = (d - hoy).days
        if 0 <= dias <= args.days:
            pos_str = f"Posición: USD {val:,.0f}. " if val > 0 else "Watchlist tier1 (sin posición). "
            alerts.append({
                "categoria":  "earnings_proximos",
                "severidad":  "media" if val > 5000 else "info",
                "activo":     tk,
                "titulo":     f"EARNINGS: {tk} reporta en {dias} día(s) ({d.strftime('%d/%m')})",
                "mensaje":    f"{tk} reporta resultados el {d.isoformat()}. {pos_str}"
                              f"Decidir ANTES: ¿agregar en debilidad post-earnings, "
                              f"mantener sin actuar, o reducir exposición?",
                "metricas":   {"fecha_earnings": d.isoformat(), "dias": dias,
                               "valor_posicion_usd": round(val, 0)},
                "sugerencia": "Regla base: NO comprar 1-2 días antes de earnings (coin flip). "
                              "Esperar el print y comprar la sobre-reacción si la tesis se confirma.",
            })
            print(f"  {tk}: earnings {d.isoformat()} ({dias}d) — USD {val:,.0f}")

    print(f"\nTotal: {len(alerts)} earnings próximos")

    if args.dry_run:
        print("DRY RUN — no se guardó nada")
        return

    sb = get_client()
    # Desactivar TODAS las earnings previas (los earnings que pasaron no
    # deben quedar activos como zombies)
    try:
        sb.table("portfolio_alerts").update({"activo_alerta": False}) \
          .eq("activo_alerta", True).eq("categoria", "earnings_proximos").execute()
    except Exception:
        pass
    if alerts:
        ins = 0
        for a in alerts:
            try:
                sb.table("portfolio_alerts").insert(a).execute()
                ins += 1
            except Exception as e:
                print(f"  {a['activo']}: {str(e)[:80]}")
        print(f"Insertadas: {ins}")
    print("=" * 60)


if __name__ == "__main__":
    main()
