# ============================================================
# BACKTEST RULES v1 — ¿Las reglas de dip hubieran funcionado?
#
# Corre las reglas del detector (dips z-gated + RSI2) sobre la
# historia de tu universo y mide retornos forward a +5/+20/+60
# días vs el baseline del ticker. Responde:
#   - ¿Comprar los dips que alertamos habría ganado plata?
#   - ¿Qué regla tiene mejor razón señal/ruido?
#
# Herramienta ad-hoc (NO va en el workflow diario).
#
# Uso:
#   python -m intelligence.backtest_rules
#   python -m intelligence.backtest_rules --period 5y
# ============================================================

import sys, argparse, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import yaml
import numpy as np
import pandas as pd
from pathlib import Path

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"

# Parámetros espejo de rules.yaml (duplicados a propósito: el backtest
# debe poder variar params sin tocar producción)
RULES = {
    "small_dip":  {"window": 5,  "pct": -10, "z_gate": -1.5},
    "medium_dip": {"window": 20, "pct": -15, "z_gate": -1.5},
    "large_dip":  {"window": 60, "pct": -25, "z_gate": -1.5},
    "rsi2":       {"rsi2_max": 10},
}
Z_ALONE, Z_ALONE_PCT = -2.5, -5.0
FWD = [5, 20, 60]
COOLDOWN = 5  # días entre señales del mismo tipo/ticker


def build_universe() -> list:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl = yaml.safe_load(f)
    tks = {r["ticker"] for r in wl.get("recurrente", [])}
    for i in wl.get("watchlist", {}).get("tier1", []):
        tks.add(i["ticker"])
    for etf in wl.get("etfs_core_no_alert", []):
        tks.discard(etf)
    return sorted(tks)


def rsi2_series(close: pd.Series) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/2, min_periods=2).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/2, min_periods=2).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def backtest_ticker(close: pd.Series) -> list:
    """→ list de (rule, idx_señal, fwd5, fwd20, fwd60)"""
    n = len(close)
    if n < 260:
        return []
    rets = close.pct_change()
    vol60 = rets.rolling(60).std()
    sma200 = close.rolling(200).mean()
    rsi2 = rsi2_series(close)

    events = []
    last_signal = {}

    for i in range(200, n - max(FWD)):
        p = close.iloc[i]
        fwd = {w: (close.iloc[i + w] / p - 1) * 100 for w in FWD}

        for rule, cfg in RULES.items():
            if rule == "rsi2":
                trig = rsi2.iloc[i] < cfg["rsi2_max"] and p > sma200.iloc[i]
            else:
                w = cfg["window"]
                if i < w:
                    continue
                pct = (p / close.iloc[i - w] - 1) * 100
                v = vol60.iloc[i]
                if pd.isna(v) or v <= 0:
                    continue
                z = pct / (v * np.sqrt(w) * 100)
                trig = (pct <= cfg["pct"] and z <= cfg["z_gate"]) or \
                       (z <= Z_ALONE and pct <= Z_ALONE_PCT)
                # dips chico/medio requieren tendencia intacta (como producción)
                if rule in ("small_dip", "medium_dip") and p <= sma200.iloc[i]:
                    trig = False
            if trig and i - last_signal.get(rule, -99) >= COOLDOWN:
                last_signal[rule] = i
                events.append((rule, fwd[5], fwd[20], fwd[60]))

    # Baseline: retornos incondicionales del ticker
    base = {w: ((close.shift(-w) / close - 1) * 100).dropna().mean() for w in FWD}
    return [(r, f5, f20, f60, base) for r, f5, f20, f60 in events]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2y")
    args = parser.parse_args()

    print("=" * 78)
    print(f"BACKTEST — reglas dip z-gated + RSI2 sobre universo ({args.period})")
    print("=" * 78)

    universe = build_universe()
    print(f"{len(universe)} tickers: {', '.join(universe[:15])}...")

    import yfinance as yf
    raw = yf.download(universe, period=args.period, interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    if raw.empty:
        print("Sin data.")
        return

    all_events = []
    baselines = {w: [] for w in FWD}
    for tk in universe:
        try:
            close = raw[tk]["Close"].dropna() if isinstance(raw.columns, pd.MultiIndex) \
                    else raw["Close"].dropna()
        except KeyError:
            continue
        evs = backtest_ticker(close)
        for rule, f5, f20, f60, base in evs:
            all_events.append({"rule": rule, "f5": f5, "f20": f20, "f60": f60})
        if evs:
            for w in FWD:
                baselines[w].append(evs[0][4][w])

    if not all_events:
        print("Sin señales en el período.")
        return

    df = pd.DataFrame(all_events)
    base_mean = {w: np.mean(baselines[w]) for w in FWD}

    print(f"\n{'Regla':12s} {'N':>5s} {'+5d':>8s} {'+20d':>8s} {'+60d':>8s} "
          f"{'Hit20d':>7s} {'vs base20d':>11s}")
    print("-" * 78)
    for rule, g in df.groupby("rule"):
        n = len(g)
        m5, m20, m60 = g["f5"].mean(), g["f20"].mean(), g["f60"].mean()
        hit = (g["f20"] > 0).mean() * 100
        edge = m20 - base_mean[20]
        print(f"{rule:12s} {n:>5d} {m5:>+7.2f}% {m20:>+7.2f}% {m60:>+7.2f}% "
              f"{hit:>6.0f}% {edge:>+10.2f}pp")
    print("-" * 78)
    print(f"{'BASELINE':12s} {'—':>5s} {base_mean[5]:>+7.2f}% {base_mean[20]:>+7.2f}% "
          f"{base_mean[60]:>+7.2f}%  (retorno incondicional promedio del universo)")
    print("\nLectura: si una regla no supera el baseline a +20/60d, la señal no")
    print("agrega valor sobre simplemente comprar cualquier día — recalibrarla.")
    print("=" * 78)


if __name__ == "__main__":
    main()
