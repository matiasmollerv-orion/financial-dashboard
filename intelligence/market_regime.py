# ============================================================
# MARKET REGIME v1 — Clasificador risk-on / neutral / risk-off
#
# Los profesionales condicionan TODA señal al régimen de mercado.
# Un dip de 2.5σ en risk-on es compra; el mismo dip con spreads de
# crédito abriéndose es un cuchillo cayendo.
#
# 4 señales (todas GRATIS, sin API keys):
#   1. Spread crédito high-yield (FRED BAMLH0A0HYM2, csv keyless)
#      → nivel >4.5% o subida >0.5pp en 20d = estrés
#   2. Curva de tasas 10y-2y (FRED T10Y2Y)
#      → invertida = precaución
#   3. SPY vs SMA200 (yfinance)
#      → bajo la media = tendencia rota
#   4. VIX (yfinance ^VIX)
#      → >25 = miedo
#
# puntos_estres 0-1 → risk_on | 2 → neutral | 3-4 → risk_off
#
# opportunity_detector lo consume para modular sugerencias y sizing.
# CERO llamadas a APIs pagadas.
#
# Uso: python -m intelligence.market_regime
# ============================================================

import sys, io, warnings
from datetime import date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd


def _fred_series(series_id: str, days: int = 120) -> pd.Series:
    """Serie FRED via fredgraph.csv (endpoint público, sin API key)."""
    import requests
    start = (date.today() - timedelta(days=days)).isoformat()
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
           f"?id={series_id}&cosd={start}")
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    col = df.columns[-1]
    df[col] = pd.to_numeric(df[col], errors="coerce")
    s = df.set_index(df.columns[0])[col].dropna()
    return s


def _yf_last_vs_sma200(ticker: str):
    """(precio_actual, sma200) o (None, None)."""
    import yfinance as yf
    raw = yf.download(ticker, period="1y", interval="1d", progress=False)
    if raw.empty:
        return None, None
    close = raw["Close"].squeeze()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    if len(close) < 200:
        return None, None
    return float(close.iloc[-1]), float(close.tail(200).mean())


def compute_market_regime(verbose: bool = False) -> dict:
    """Retorna {regimen, puntos_estres, senales: {...}}. Robusto: si una
    señal falla, se omite y el umbral se ajusta proporcionalmente."""
    senales = {}
    puntos = 0
    disponibles = 0

    # 1. Spread HY
    try:
        hy = _fred_series("BAMLH0A0HYM2")
        nivel = float(hy.iloc[-1])
        delta_20d = nivel - float(hy.iloc[-min(20, len(hy))])
        estres = nivel > 4.5 or delta_20d > 0.5
        senales["credito_hy"] = {"nivel_pct": round(nivel, 2),
                                 "delta_20d_pp": round(delta_20d, 2),
                                 "estres": estres}
        puntos += estres
        disponibles += 1
    except Exception as e:
        senales["credito_hy"] = {"error": str(e)[:60]}

    # 2. Curva 10y-2y
    try:
        curva = _fred_series("T10Y2Y")
        nivel = float(curva.iloc[-1])
        estres = nivel < 0
        senales["curva_10y2y"] = {"nivel_pp": round(nivel, 2), "estres": estres}
        puntos += estres
        disponibles += 1
    except Exception as e:
        senales["curva_10y2y"] = {"error": str(e)[:60]}

    # 3. SPY vs SMA200
    try:
        p, sma = _yf_last_vs_sma200("SPY")
        if p is not None:
            estres = p < sma
            senales["spy_sma200"] = {"precio": round(p, 2), "sma200": round(sma, 2),
                                     "pct_vs_sma": round((p / sma - 1) * 100, 1),
                                     "estres": estres}
            puntos += estres
            disponibles += 1
    except Exception as e:
        senales["spy_sma200"] = {"error": str(e)[:60]}

    # 4. VIX
    try:
        import yfinance as yf
        vix_raw = yf.download("^VIX", period="1mo", interval="1d", progress=False)
        if not vix_raw.empty:
            v = vix_raw["Close"].squeeze()
            if isinstance(v, pd.DataFrame):
                v = v.iloc[:, 0]
            nivel = float(v.dropna().iloc[-1])
            estres = nivel > 25
            senales["vix"] = {"nivel": round(nivel, 1), "estres": estres}
            puntos += estres
            disponibles += 1
    except Exception as e:
        senales["vix"] = {"error": str(e)[:60]}

    # Clasificación (umbral proporcional a señales disponibles)
    if disponibles == 0:
        regimen = "neutral"  # sin datos, no opinar fuerte
    else:
        ratio = puntos / disponibles
        if ratio >= 0.75:
            regimen = "risk_off"
        elif ratio >= 0.5:
            regimen = "neutral"
        else:
            regimen = "risk_on"

    result = {"regimen": regimen, "puntos_estres": puntos,
              "senales_disponibles": disponibles, "senales": senales}
    if verbose:
        print(f"Régimen: {regimen.upper()} ({puntos}/{disponibles} señales en estrés)")
        for k, v in senales.items():
            print(f"  {k}: {v}")
    return result


def regime_label(r: dict) -> str:
    """Línea humana para el email."""
    reg = r["regimen"]
    emoji = {"risk_on": "🟢", "neutral": "🟡", "risk_off": "🔴"}[reg]
    nombre = {"risk_on": "Risk-ON", "neutral": "Neutral", "risk_off": "RISK-OFF"}[reg]
    det = []
    s = r["senales"]
    if "credito_hy" in s and "nivel_pct" in s["credito_hy"]:
        det.append(f"HY {s['credito_hy']['nivel_pct']}%")
    if "vix" in s and "nivel" in s["vix"]:
        det.append(f"VIX {s['vix']['nivel']}")
    if "spy_sma200" in s and "pct_vs_sma" in s["spy_sma200"]:
        det.append(f"SPY {s['spy_sma200']['pct_vs_sma']:+.1f}% vs SMA200")
    return f"{emoji} Régimen {nombre} ({r['puntos_estres']}/{r['senales_disponibles']} señales en estrés: {', '.join(det)})"


if __name__ == "__main__":
    r = compute_market_regime(verbose=True)
    print("\n" + regime_label(r))
