# ============================================================
# EARLY WARNING v1 — Anticipación, no confirmación
#
# Pedido explícito de Matías (15 jul 2026): "quiero ANTICIPARME, no vender
# cuando ya estoy 20% abajo". Un stop-loss de precio es reactivo por
# definición — solo dispara DESPUÉS de que la caída ya pasó. Este módulo
# combina señales LÍDER (que históricamente preceden caídas, no las
# confirman) en un score compuesto, para las posiciones core de IA que
# más preocupan a Matías (NVDA, GOOGL, MSFT, TSM, ASML).
#
# Investigación real detrás de cada señal — ver investor_profile.yaml
# sección sistema_alerta_temprana para las citas completas:
#   - Régimen de mercado (spreads + curva + VIX): 4-8 meses de anticipación
#     documentados (Fed Reserve research). Reutiliza market_regime.py.
#   - 13F en AGREGADO (2+ fondos reduciendo la misma posición): +12%/año
#     de alpha documentado (2007-2024), pero ~46 días de rezago — señal
#     de cambio de tesis, no de timing fino.
#   - Divergencia RSI: señal líder real pero ruidosa sola.
#   - Valoración estirada (PEG): heurística de Lynch, PEG >> 1 = caro
#     relativo a su propio crecimiento.
#   - Debilidad sectorial temprana: pares del mismo rol mostrando estrés
#     antes que el ticker principal.
#
# Insider selling INDIVIDUAL fue evaluado y DESCARTADO — evidencia
# académica (Lakonishok & Lee) muestra que es una señal débil (insiders
# venden por razones no informativas: diversificación, impuestos, planes
# 10b5-1). No se usa.
#
# NO hay gate de ganancia mínima — aplica gane o pierda la posición.
# Ninguna señal dispara sola una alerta — se necesita el score compuesto.
#
# CERO llamadas a la API de Anthropic.
#
# Uso:
#   python -m intelligence.early_warning
#   python -m intelligence.early_warning --dry-run
# ============================================================

import sys, time, argparse, warnings
from datetime import date, timedelta
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

from database.supabase_client import get_client
from intelligence.market_regime import compute_market_regime
from intelligence.edgar_monitor import _get, _fetch_13f_holdings, match_ticker, THROTTLE

PROFILE_PATH = Path(__file__).parent / "config" / "investor_profile.yaml"
WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"

# Pares del mismo rol/sector — para detectar debilidad temprana que aún
# no le pega al ticker principal. No requiere que Matías los posea.
PEERS = {
    "NVDA": ["AMD", "AVGO", "TSM", "MU"],
    "GOOGL": ["MSFT", "META", "AMZN"],
    "MSFT": ["GOOGL", "AMZN", "ORCL"],
    "TSM": ["ASML", "NVDA", "AMD"],
    "ASML": ["TSM", "LRCX", "KLAC"],
}


def load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── SEÑAL 1: valoración estirada (PEG, heurística de Lynch) ────
def señal_valoracion(ticker: str) -> dict:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        pe = info.get("forwardPE")
        growth = info.get("revenueGrowth")
        peg = info.get("pegRatio")
        if peg is None and pe and growth and growth > 0:
            peg = pe / (growth * 100)
        activa = peg is not None and peg > 2.0
        return {"activa": activa, "peg": round(peg, 2) if peg else None, "pe_fwd": pe}
    except Exception:
        return {"activa": False, "peg": None, "error": True}


# ── SEÑAL 2: divergencia de momentum (precio nuevo máx, RSI no confirma) ─
def señal_divergencia(close: pd.Series, ventana: int = 60) -> dict:
    if len(close) < ventana:
        return {"activa": False}
    sub = close.tail(ventana)
    delta = sub.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).dropna()
    if len(rsi) < 20:
        return {"activa": False}

    idx_max_precio = sub.tail(len(rsi)).idxmax()
    idx_max_rsi = rsi.idxmax()
    precio_reciente = sub.index[-1] - sub.index[-10] <= timedelta(days=14)
    # Divergencia: el máximo de precio es reciente (últimos 10 días) pero
    # el máximo de RSI fue hace más de 20 días Y el RSI actual está
    # claramente por debajo de ese máximo previo (perdiendo momentum)
    dias_desde_max_rsi = (rsi.index[-1] - idx_max_rsi).days
    precio_cerca_max = sub.iloc[-1] >= sub.tail(10).max() * 0.98
    activa = (precio_cerca_max and dias_desde_max_rsi > 20
             and rsi.iloc[-1] < rsi.loc[idx_max_rsi] * 0.85)
    return {"activa": bool(activa), "rsi_actual": round(rsi.iloc[-1], 1),
            "rsi_max_previo": round(rsi.loc[idx_max_rsi], 1),
            "dias_desde_max_rsi": dias_desde_max_rsi}


# ── SEÑAL 3: debilidad sectorial temprana (pares del mismo rol) ────
def señal_sectorial(ticker: str, precios: dict) -> dict:
    peers = PEERS.get(ticker, [])
    if not peers or ticker not in precios:
        return {"activa": False}
    mom_ticker = precios[ticker]
    moms_peers = [precios[p] for p in peers if p in precios]
    if not moms_peers:
        return {"activa": False}
    prom_peers = float(np.mean(moms_peers))
    # Activa si los pares están mostrando debilidad clara (momentum 20d
    # negativo en promedio) mientras el ticker principal aún no
    activa = prom_peers < -5 and mom_ticker > prom_peers + 5
    return {"activa": bool(activa), "momentum_ticker_20d": round(mom_ticker, 1),
            "momentum_pares_prom_20d": round(prom_peers, 1), "peers": peers}


# ── SEÑAL 4: reducción en cluster de 13F (2+ fondos, no individual) ────
def fetch_13f_reducciones_todos_fondos(tickers: list, days: int, wl_cfg: dict) -> dict:
    """UN solo pase por los 15 fondos (no uno por ticker) — evita 75
    llamadas a SEC cuando bastan 15. Retorna {ticker: {n_fondos, fondos}}."""
    reducciones = {tk: {"n_fondos_redujeron": 0, "fondos": []} for tk in tickers}
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    for fund in wl_cfg.get("smart_money_funds", []):
        try:
            cik = int(fund["cik"])
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", [])
            f13 = [(dates[i], accs[i]) for i, f in enumerate(forms) if f == "13F-HR"]
            if len(f13) < 2 or f13[0][0] < cutoff:
                continue  # sin 13F previo para comparar, o sin filing nuevo en la ventana

            curr = _fetch_13f_holdings(cik, f13[0][1])
            prev = _fetch_13f_holdings(cik, f13[1][1])
            for tk in tickers:
                curr_val = sum(v for issuer, v in curr.items() if match_ticker(issuer) == tk)
                prev_val = sum(v for issuer, v in prev.items() if match_ticker(issuer) == tk)
                if prev_val > 0 and (curr_val == 0 or curr_val <= prev_val * 0.5):
                    reducciones[tk]["n_fondos_redujeron"] += 1
                    reducciones[tk]["fondos"].append(fund["nombre"])
        except Exception:
            continue
    return reducciones


def señal_13f_cluster(ticker: str, reducciones_todos: dict) -> dict:
    r = reducciones_todos.get(ticker, {"n_fondos_redujeron": 0, "fondos": []})
    return {"activa": r["n_fondos_redujeron"] >= 2, **r}


# ── COMPOSITE ────────────────────────────────────────────────
def evaluar_ticker(ticker: str, close: pd.Series, precios_momentum: dict,
                   regimen: dict, reducciones_13f: dict) -> dict:
    s_val = señal_valoracion(ticker)
    s_div = señal_divergencia(close)
    s_sec = señal_sectorial(ticker, precios_momentum)
    s_13f = señal_13f_cluster(ticker, reducciones_13f)
    s_reg = {"activa": regimen["regimen"] in ("neutral", "risk_off")}

    pesos = {"valoracion_estirada": 1.0, "divergencia_momentum": 1.0,
            "debilidad_sectorial_temprana": 1.0, "reduccion_13f_cluster": 1.5,
            "regimen_mercado": 1.5}
    señales = {"valoracion_estirada": s_val, "divergencia_momentum": s_div,
              "debilidad_sectorial_temprana": s_sec, "reduccion_13f_cluster": s_13f,
              "regimen_mercado": s_reg}

    score = sum(pesos[k] for k, v in señales.items() if v.get("activa"))
    activas = [k for k, v in señales.items() if v.get("activa")]
    return {"ticker": ticker, "score": score, "señales_activas": activas,
            "detalle": señales}


SCORE_MAXIMO = 1.0 + 1.0 + 1.0 + 1.5 + 1.5  # suma de todos los pesos posibles


def build_alert(res: dict, umbral: float) -> dict:
    tk = res["ticker"]
    activas = res["señales_activas"]
    labels = {
        "valoracion_estirada": "valoración estirada (PEG alto)",
        "divergencia_momentum": "divergencia de momentum (RSI no confirma nuevo máximo)",
        "debilidad_sectorial_temprana": "pares del sector mostrando debilidad",
        "reduccion_13f_cluster": "múltiples fondos smart money redujeron la posición",
        "regimen_mercado": "régimen de mercado virando a neutral/risk-off",
    }
    detalle_txt = "; ".join(labels[k] for k in activas)
    # Score reescalado a 0-100 para ser comparable con el resto de las
    # alertas del sistema (opportunity_detector usa esa escala) — si no,
    # esto siempre quedaría al fondo del email por escala, no por importancia.
    score_100 = round(res["score"] / SCORE_MAXIMO * 100)
    return {
        "categoria": "alerta_temprana",
        "severidad": "alta" if res["score"] >= umbral + 1 else "media",
        "activo": tk,
        "titulo": f"ALERTA TEMPRANA: {tk} — {len(activas)} señales líder activas",
        "mensaje": f"{tk} acumula {len(activas)} señal(es) líder: {detalle_txt}. "
                   f"Esto NO es un stop-loss — es anticipación. Ninguna señal individual "
                   f"justifica vender, pero la combinación amerita revisar la tesis ahora, "
                   f"antes de que el precio ya haya caído.",
        "metricas": {"score": score_100, "score_raw": res["score"], "señales_activas": activas,
                     "detalle": res["detalle"]},
        "sugerencia": "Revisar tesis. Si decides recortar, hazlo parcial (15-25%) y deja el "
                      "resto — el objetivo es tener caja para comprar más abajo si la corrección "
                      "se profundiza, no salir de la convicción.",
    }


# ── SAVE ────────────────────────────────────────────────────
def save_alerts(alerts: list) -> dict:
    sb = get_client()
    ins = err = 0
    try:
        sb.table("portfolio_alerts").update({"activo_alerta": False}) \
          .eq("activo_alerta", True).eq("categoria", "alerta_temprana").execute()
    except Exception:
        pass
    for a in alerts:
        try:
            sb.table("portfolio_alerts").insert(a).execute()
            ins += 1
        except Exception as e:
            err += 1
            print(f"  {a['activo']}: {str(e)[:100]}")
    return {"insertadas": ins, "errores": err}


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days-13f", type=int, default=14)
    args = parser.parse_args()

    print("=" * 60)
    print("EARLY WARNING v1 — Anticipación, no confirmación")
    print("=" * 60)

    profile = load_profile()
    sat = profile.get("sistema_alerta_temprana", {})
    tickers = sat.get("aplica_a", ["NVDA", "GOOGL", "MSFT", "TSM", "ASML"])
    umbral = sat.get("umbral_alerta", 2.5)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl_cfg = yaml.safe_load(f)

    print("\nClasificando régimen de mercado...")
    regimen = compute_market_regime()
    print(f"  {regimen['regimen'].upper()} ({regimen['puntos_estres']}/{regimen['senales_disponibles']} señales en estrés)")

    print(f"\nDescargando precios de {tickers} + pares...")
    todos = set(tickers)
    for tk in tickers:
        todos.update(PEERS.get(tk, []))
    import yfinance as yf
    raw = yf.download(sorted(todos), period="1y", interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")

    closes = {}
    momentum_20d = {}
    for tk in todos:
        try:
            c = raw[tk]["Close"].dropna()
            if len(c) >= 60:
                closes[tk] = c
                momentum_20d[tk] = (c.iloc[-1] / c.iloc[-min(21, len(c))] - 1) * 100
        except Exception:
            continue

    print(f"\nRevisando 13F de {len(wl_cfg.get('smart_money_funds', []))} fondos smart money "
          f"(un solo pase para los {len(tickers)} tickers)...")
    reducciones_13f = fetch_13f_reducciones_todos_fondos(tickers, args.days_13f, wl_cfg)

    print(f"\nEvaluando {len(tickers)} posiciones core IA...")
    resultados = []
    for tk in tickers:
        if tk not in closes:
            print(f"  {tk}: sin datos de precio")
            continue
        res = evaluar_ticker(tk, closes[tk], momentum_20d, regimen, reducciones_13f)
        resultados.append(res)
        print(f"  {tk}: score {res['score']} — {res['señales_activas'] or 'sin señales activas'}")

    alerts = [build_alert(r, umbral) for r in resultados if r["score"] >= umbral]
    print(f"\nTotal alertas tempranas: {len(alerts)} (umbral {umbral})")

    if args.dry_run:
        print("DRY RUN — no se guardó nada")
        return
    result = save_alerts(alerts)
    print(f"Insertadas: {result['insertadas']} | Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
