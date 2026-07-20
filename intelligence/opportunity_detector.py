# ============================================================
# OPPORTUNITY DETECTOR v2 — Watchlist + Cartera + Connors Rules
#
# Carga watchlist.yaml (fuente de verdad) y aplica:
#   1. Connors DIP rules sobre posiciones + watchlist
#   2. Entry target checks para Tier 1 watchlist
#   3. Acciones pendientes recordatorio
#   4. Momentum warnings
#
# NO compra — solo genera alertas en portfolio_alerts.
# El daily_brief luego prioriza y selecciona las top 5.
#
# Uso:
#   python -m intelligence.opportunity_detector
#   python -m intelligence.opportunity_detector --dry-run
# ============================================================

import sys, os, argparse, warnings
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


RULES_PATH = Path(__file__).parent / "config" / "rules.yaml"
WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"


def get_usdclp() -> float:
    """Tipo de cambio actual via yfinance (con fallback)."""
    try:
        import yfinance as yf
        fx = yf.download("USDCLP=X", period="5d", interval="1d", progress=False)
        if not fx.empty:
            val = fx["Close"].squeeze()
            if isinstance(val, pd.DataFrame):
                val = val.iloc[:, 0]
            return float(val.iloc[-1])
    except Exception:
        pass
    return 901.76


USD_CLP = get_usdclp()


# ── LOADERS ─────────────────────────────────────────────────
def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_watchlist_config() -> dict:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


PROFILE_PATH = Path(__file__).parent / "config" / "investor_profile.yaml"


def load_profile() -> dict:
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


# ── SIZING POR RIESGO ───────────────────────────────────────
def monto_por_riesgo(vol_diaria_pct, sizing: dict, portfolio_usd: float,
                     mult: float = 1.0, regimen: str = "neutral") -> tuple:
    """Monto que iguala el RIESGO entre compras: monto = riesgo_presupuestado / σ_mensual.
    Misma plata en un ticker de vol 80% arriesga 4× más que en uno de 20%."""
    import math
    lo_min = sizing.get("monto_min_usd", 100)
    hi_max = sizing.get("monto_max_usd", 1000)
    if not vol_diaria_pct or not portfolio_usd:
        return (150, 250)
    sigma_mensual = vol_diaria_pct / 100 * math.sqrt(21)
    riesgo_usd = portfolio_usd * sizing.get("riesgo_por_compra_pct", 0.5) / 100
    base = riesgo_usd / max(sigma_mensual, 0.01) * mult
    if regimen == "risk_off":
        base *= sizing.get("factor_risk_off", 0.5)
    # Clamp AMBOS extremos a [min, max] (el techo es el cash mensual disponible)
    lo = min(max(base * 0.8, lo_min), hi_max)
    hi = min(max(base * 1.2, lo), hi_max)
    lo = int(round(lo / 10) * 10)
    hi = int(max(round(hi / 10) * 10, lo))
    return (lo, hi)


def fmt_monto_riesgo(lo: int, hi: int, sizing: dict) -> str:
    """Formatea el monto evitando el rango degenerado 'USD 1000-1000':
    eso pasa cuando el sizing por volatilidad pide MÁS que el tope mensual
    disponible — no es un error, pero mostrar un rango falso confunde."""
    hi_max = sizing.get("monto_max_usd", 1000) if sizing else 1000
    if lo == hi:
        if hi >= hi_max:
            return f"USD {hi} (tope de tu presupuesto mensual — el sizing por volatilidad pediría más)"
        return f"USD {hi}"
    return f"USD {lo}-{hi}"


# ── GATE FUNDAMENTAL (anti-cuchillo-cayendo) ────────────────
def check_fundamentals(ticker: str, especulativos: set) -> dict:
    """Chequeo barato de deterioro fundamental via yfinance (solo para
    tickers que YA dispararon un dip — pocas llamadas por corrida).
    El error retail #1 es promediar a la baja en negocios que se deterioran."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {"estado": "sin_datos"}
    if info.get("quoteType") != "EQUITY":
        return {"estado": "etf"}  # ETFs: diversificados, sin gate
    debilidades = []
    rg = info.get("revenueGrowth")
    if rg is not None and rg < -0.05:
        debilidades.append(f"ingresos {rg*100:.0f}% YoY")
    pm = info.get("profitMargins")
    # A las especulativas no les exigimos margen (pre-profit por definición),
    # pero ingresos cayendo es mala señal en cualquier etapa
    if ticker not in especulativos and pm is not None and pm < -0.15:
        debilidades.append(f"margen {pm*100:.0f}%")
    return {"estado": "debil" if debilidades else "ok", "notas": debilidades}


def load_cartera() -> pd.DataFrame:
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return df
    for c in ["cantidad", "precio_compra", "precio_actual"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["valor_usd"] = df["cantidad"] * df["precio_actual"]
    df["valor_clp"] = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP,
        axis=1,
    )
    return df


def yf_ticker_for(ticker: str, mercado: str) -> str:
    if mercado == "nacional":
        # Strip _STG (Santander Corredora) para lookup válido en yfinance
        base = ticker.replace("_STG", "") if ticker.endswith("_STG") else ticker
        return f"{base}.SN"
    if mercado == "crypto":
        return f"{ticker}-USD"
    return ticker


# ── PRICE DATA ──────────────────────────────────────────────
def fetch_history(yf_tickers: list, period: str = "1y") -> pd.DataFrame:
    try:
        import yfinance as yf
        raw = yf.download(
            yf_tickers, period=period, interval="1d",
            auto_adjust=True, progress=False, group_by="ticker",
        )
        return raw
    except Exception as e:
        print(f"  yfinance error: {e}")
        return pd.DataFrame()


def get_ticker_series(raw, yf_tk):
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if yf_tk in raw.columns.get_level_values(0):
                sub = raw[yf_tk]
                return sub.get("Close", None), sub.get("Volume", None)
            return None, None
        else:
            return raw.get("Close", None), raw.get("Volume", None)
    except Exception:
        return None, None


# ── METRICS ─────────────────────────────────────────────────
def calc_metrics(close: pd.Series, volume: pd.Series) -> dict:
    if close is None or len(close.dropna()) < 20:
        return None
    close = close.dropna()
    m = {
        "precio_actual": float(close.iloc[-1]),
        "precio_5d_atras":  float(close.iloc[-min(6, len(close))]) if len(close) >= 6 else None,
        "precio_20d_atras": float(close.iloc[-min(21, len(close))]) if len(close) >= 21 else None,
        "precio_60d_atras": float(close.iloc[-min(61, len(close))]) if len(close) >= 61 else None,
        "ath_252d":         float(close.tail(252).max()) if len(close) > 0 else None,
    }
    p = m["precio_actual"]
    m["pct_5d"]  = ((p / m["precio_5d_atras"]  - 1) * 100) if m["precio_5d_atras"]  else None
    m["pct_20d"] = ((p / m["precio_20d_atras"] - 1) * 100) if m["precio_20d_atras"] else None
    m["pct_60d"] = ((p / m["precio_60d_atras"] - 1) * 100) if m["precio_60d_atras"] else None
    m["pct_from_ath"] = ((p / m["ath_252d"] - 1) * 100) if m["ath_252d"] else None

    if len(close) >= 200:
        sma200 = float(close.tail(200).mean())
        m["sma200"] = sma200
        m["above_sma200"] = p > sma200
    else:
        m["sma200"] = None
        m["above_sma200"] = None

    m["sma50"] = float(close.tail(50).mean()) if len(close) >= 50 else None
    m["low_60d"] = float(close.tail(60).min()) if len(close) >= 30 else None

    if volume is not None and len(volume.dropna()) >= 60:
        vol_recent = float(volume.tail(5).mean())
        vol_avg    = float(volume.tail(60).mean())
        m["volume_ratio"] = (vol_recent / vol_avg) if vol_avg > 0 else None
    else:
        m["volume_ratio"] = None

    # ── Volatilidad propia + z-scores ────────────────────────
    # Una caída de -10% en un ticker volátil (IONQ) es ruido normal;
    # en uno estable (UNH) es un evento. El z-score normaliza por la
    # volatilidad diaria de cada ticker escalada a la ventana.
    rets = close.pct_change().dropna().tail(60)
    if len(rets) >= 30:
        vol_d = float(rets.std())
        m["vol_diaria_pct"] = vol_d * 100
        for window, key in [(5, "pct_5d"), (20, "pct_20d"), (60, "pct_60d")]:
            pct = m.get(key)
            sigma_w = vol_d * np.sqrt(window) * 100
            m[f"z_{window}d"] = (pct / sigma_w) if (pct is not None and sigma_w > 0) else None
    else:
        m["vol_diaria_pct"] = None
        m["z_5d"] = m["z_20d"] = m["z_60d"] = None

    # ── RSI(2) — el indicador real de Connors ────────────────
    # Mean-reversion: RSI(2) < 10 sobre SMA200 = pullback comprable
    # en tendencia alcista. RSI(2) > 95 = sobreextendido.
    if len(close) >= 10:
        delta = close.diff().dropna().tail(30)
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/2, min_periods=2).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=1/2, min_periods=2).mean().iloc[-1]
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            m["rsi2"] = float(100 - 100 / (1 + rs))
        else:
            m["rsi2"] = 100.0
    else:
        m["rsi2"] = None

    return m


# ── CONNORS DIP RULES ──────────────────────────────────────
def evaluate_connors_rules(ticker: str, m: dict, rules: dict,
                           tesis: str = "", bucket: str = "",
                           conviction: str = "cartera",
                           ctx: dict = None) -> list:
    """Aplica reglas Connors sobre un ticker. Retorna list[dict] de alertas.

    conviction: "cartera" | "recurrente" | "tier1" | "tier2" | "tier3"
      - cartera/recurrente/tier1: sugerencia = COMPRAR con monto
      - tier2: sugerencia = EVALUAR COMPRA (oportunístico)
      - tier3: sugerencia = EVALUAR solamente (seguimiento, sin acción)
    """
    alerts = []
    # Contexto de sizing/régimen (guardar ANTES de reutilizar el nombre ctx
    # como etiqueta de bucket más abajo)
    sctx = ctx if isinstance(ctx, dict) else {}
    dips = rules.get("dips", {})
    momentum = rules.get("momentum", {})
    ctx = f" [{bucket}]" if bucket else ""
    tesis_note = f" Tesis: {tesis}" if tesis else ""

    # Ajustar sugerencia y severidad según nivel de convicción
    is_actionable = conviction in ("cartera", "recurrente", "tier1")
    is_tier2 = conviction == "tier2"
    # tier3 = solo evaluar

    sizing = sctx.get("sizing", {})
    portfolio_usd = sctx.get("portfolio_usd", 0)
    regimen = sctx.get("regimen", "neutral")
    prefijo_regimen = ("⚠️ RISK-OFF: caída probablemente sistémica, no idiosincrática. "
                       if regimen == "risk_off" else "")

    def _sugerencia_dip(rule_name, rule_cfg):
        # Monto por RIESGO (vol propia del ticker), no fijo
        if sizing and portfolio_usd:
            lo, hi = monto_por_riesgo(m.get("vol_diaria_pct"), sizing, portfolio_usd,
                                      mult=rule_cfg.get("sizing_mult", 1.0),
                                      regimen=regimen)
        else:
            lo = rule_cfg.get("accion_min_usd", 150)
            hi = rule_cfg.get("accion_max_usd", 250)
        monto_fmt = fmt_monto_riesgo(lo, hi, sizing)
        if is_actionable:
            if rule_name == "small_dip":
                return f"{prefijo_regimen}Considerar compra {monto_fmt} (sizing por vol)."
            elif rule_name == "medium_dip":
                return f"{prefijo_regimen}Compra puntual {monto_fmt} si tesis intacta (sizing por vol)."
            elif rule_name == "large_dip":
                return f"{prefijo_regimen}Oportunidad agresiva {monto_fmt} (sizing por vol)."
            elif rule_name == "bear_crash":
                return f"{prefijo_regimen}MANUAL REVIEW. Si tesis viva, compra {monto_fmt}."
        elif is_tier2:
            return f"{prefijo_regimen}Evaluar compra oportunística. Entry si tesis OK."
        else:  # tier3
            return f"Solo seguimiento. Evaluar si tesis mejora para subir a Tier 2."

    def _severidad(base_sev):
        """Tier 3 baja severidad; Tier 2 mantiene; cartera/recurrente/tier1 normal."""
        if conviction == "tier3":
            return "info" if base_sev == "media" else "media"
        return base_sev

    # ── Gating por z-score (volatilidad propia del ticker) ───
    # Vía 1: cruza el % fijo Y el move es ≥ |z_gate|σ → filtra ruido en volátiles
    # Vía 2: move ≥ |z_alone|σ aunque no cruce el % fijo → detecta eventos en estables
    zcfg = rules.get("zscore", {})
    z_gate = zcfg.get("min_z_with_threshold", -1.5)
    z_alone = zcfg.get("standalone_z", -2.5)
    z_alone_min_pct = zcfg.get("standalone_min_pct", -5.0)

    def _dip_significativo(pct, z, threshold):
        if pct is None:
            return False
        if pct <= threshold and (z is None or z <= z_gate):
            return True
        if z is not None and z <= z_alone and pct <= z_alone_min_pct:
            return True
        return False

    def _z_note(z):
        return f" ({abs(z):.1f}σ de su vol normal)" if z is not None else ""

    # 1. DIP CHICO (-10% en 5d, ajustado por volatilidad)
    rule = dips.get("small_dip", {})
    if _dip_significativo(m["pct_5d"], m.get("z_5d"), rule.get("threshold_pct", -10)):
        ok = True
        if rule.get("require_above_sma200") and m["above_sma200"] is False:
            ok = False
        if rule.get("require_volume_ratio") and m["volume_ratio"] is not None:
            if m["volume_ratio"] < rule["require_volume_ratio"]:
                ok = False
        if ok:
            alerts.append({
                "categoria":  "oportunidad_dip",
                "severidad":  _severidad("media"),
                "activo":     ticker,
                "titulo":     f"DIP CHICO en {ticker}{ctx}",
                "mensaje":    f"{ticker} cayo {m['pct_5d']:.1f}% en 5d{_z_note(m.get('z_5d'))}. "
                              f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
                "metricas":   {"pct_5d": round(m["pct_5d"], 2), "precio": m["precio_actual"],
                               "z_5d": round(m["z_5d"], 2) if m.get("z_5d") else None,
                               "rsi2": round(m["rsi2"], 1) if m.get("rsi2") is not None else None,
                               "bucket": bucket, "rule": "small_dip", "conviction": conviction},
                "sugerencia": _sugerencia_dip("small_dip", rule),
            })

    # 2. DIP MEDIO (-15% en 20d, ajustado por volatilidad)
    rule = dips.get("medium_dip", {})
    if _dip_significativo(m["pct_20d"], m.get("z_20d"), rule.get("threshold_pct", -15)):
        ok = True
        if rule.get("require_above_sma200") and m["above_sma200"] is False:
            ok = False
        if ok:
            alerts.append({
                "categoria":  "oportunidad_dip",
                "severidad":  _severidad("alta"),
                "activo":     ticker,
                "titulo":     f"DIP MEDIO en {ticker}{ctx}",
                "mensaje":    f"{ticker} cayo {m['pct_20d']:.1f}% en 20d{_z_note(m.get('z_20d'))}. "
                              f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
                "metricas":   {"pct_20d": round(m["pct_20d"], 2), "precio": m["precio_actual"],
                               "z_20d": round(m["z_20d"], 2) if m.get("z_20d") else None,
                               "rsi2": round(m["rsi2"], 1) if m.get("rsi2") is not None else None,
                               "bucket": bucket, "rule": "medium_dip", "conviction": conviction},
                "sugerencia": _sugerencia_dip("medium_dip", rule),
            })

    # 3. DIP GRANDE (-25% en 60d, ajustado por volatilidad)
    rule = dips.get("large_dip", {})
    if _dip_significativo(m["pct_60d"], m.get("z_60d"), rule.get("threshold_pct", -25)):
        alerts.append({
            "categoria":  "oportunidad_dip",
            "severidad":  _severidad("alta"),
            "activo":     ticker,
            "titulo":     f"DIP GRANDE en {ticker}{ctx}",
            "mensaje":    f"{ticker} cayo {m['pct_60d']:.1f}% en 60d{_z_note(m.get('z_60d'))}. "
                          f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
            "metricas":   {"pct_60d": round(m["pct_60d"], 2), "precio": m["precio_actual"],
                           "z_60d": round(m["z_60d"], 2) if m.get("z_60d") else None,
                           "bucket": bucket, "rule": "large_dip", "conviction": conviction},
            "sugerencia": _sugerencia_dip("large_dip", rule),
        })

    # 4. BEAR CRASH (-40% desde ATH)
    rule = dips.get("bear_crash", {})
    if m["pct_from_ath"] is not None and m["pct_from_ath"] <= rule.get("threshold_pct", -40):
        alerts.append({
            "categoria":  "oportunidad_dip",
            "severidad":  _severidad("critica"),
            "activo":     ticker,
            "titulo":     f"BEAR CRASH en {ticker}{ctx}",
            "mensaje":    f"{ticker} bajo {m['pct_from_ath']:.1f}% desde ATH. "
                          f"USD {m['precio_actual']:.2f} vs ATH USD {m['ath_252d']:.2f}.{tesis_note}",
            "metricas":   {"pct_from_ath": round(m["pct_from_ath"], 2), "precio": m["precio_actual"],
                           "ath": m["ath_252d"], "bucket": bucket, "rule": "bear_crash",
                           "conviction": conviction},
            "sugerencia": _sugerencia_dip("bear_crash", rule),
        })

    # 5. MOMENTUM EXTREMO (+30% en 20d)
    rule = momentum.get("extreme_rally", {})
    if m["pct_20d"] is not None and m["pct_20d"] >= rule.get("threshold_pct", 30):
        alerts.append({
            "categoria":  "momentum_warning",
            "severidad":  _severidad("media"),
            "activo":     ticker,
            "titulo":     f"MOMENTUM EXTREMO en {ticker}{ctx}",
            "mensaje":    f"{ticker} subio +{m['pct_20d']:.1f}% en 20d. "
                          f"Precio: USD {m['precio_actual']:.2f}.",
            "metricas":   {"pct_20d": round(m["pct_20d"], 2), "precio": m["precio_actual"],
                           "rsi2": round(m["rsi2"], 1) if m.get("rsi2") is not None else None,
                           "bucket": bucket, "rule": "extreme_rally", "conviction": conviction},
            "sugerencia": "NO comprar. Evaluar trim parcial 25-30%.",
        })

    # 6. CONNORS RSI(2) — pullback comprable en tendencia alcista
    # El setup clásico de Connors: RSI(2) < 10 con precio sobre SMA200.
    # Mean-reversion de corto plazo en tendencia larga intacta.
    mr = rules.get("mean_reversion", {}).get("rsi2_pullback", {})
    rsi2 = m.get("rsi2")
    rsi2_max = mr.get("rsi2_max", 10)
    if (rsi2 is not None and rsi2 < rsi2_max
            and m.get("above_sma200")
            and conviction in ("cartera", "recurrente", "tier1", "tier2")):
        if is_actionable:
            if sizing and portfolio_usd:
                lo_r, hi_r = monto_por_riesgo(m.get("vol_diaria_pct"), sizing, portfolio_usd,
                                              mult=mr.get("sizing_mult", 0.6), regimen=regimen)
                monto_fmt_r = fmt_monto_riesgo(lo_r, hi_r, sizing)
            else:
                monto_fmt_r = "USD 100-250"
            sug = f"Pullback comprable: agregar {monto_fmt_r} en la ventana de 1-3 días (sizing por vol)."
        else:
            sug = "Evaluar entry oportunístico."
        alerts.append({
            "categoria":  "oportunidad_rsi2",
            "severidad":  _severidad("media"),
            "activo":     ticker,
            "titulo":     f"RSI(2) PULLBACK en {ticker}{ctx}",
            "mensaje":    f"{ticker} con RSI(2) = {rsi2:.0f} sobre SMA200 "
                          f"(setup Connors: sobreventa extrema de corto plazo en "
                          f"tendencia alcista intacta). "
                          f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
            "metricas":   {"rsi2": round(rsi2, 1), "precio": m["precio_actual"],
                           "sma200": round(m["sma200"], 2) if m.get("sma200") else None,
                           "bucket": bucket, "rule": "rsi2_pullback", "conviction": conviction},
            "sugerencia": sug,
        })

    return alerts


# ── WATCHLIST ENTRY TARGET CHECK ────────────────────────────
def check_entry_targets(watchlist_cfg: dict, metrics_map: dict) -> list:
    """Revisa si algún ticker Tier 1 está en zona de entry target."""
    alerts = []
    tier1 = watchlist_cfg.get("watchlist", {}).get("tier1", [])

    for item in tier1:
        tk = item.get("ticker")
        entry = item.get("entry_usd")
        if not tk or not entry or entry is None:
            continue
        m = metrics_map.get(tk)
        if not m:
            continue

        precio = m["precio_actual"]
        entry_low, entry_high = entry[0], entry[1]

        if precio <= entry_high:
            size = item.get("size_usd", [300, 500])
            in_zone = precio <= entry_high and precio >= entry_low * 0.9  # 10% below low still interesting
            if in_zone:
                alerts.append({
                    "categoria":  "watchlist_entry",
                    "severidad":  "alta",
                    "activo":     tk,
                    "titulo":     f"ENTRY TARGET: {tk} a USD {precio:.2f}",
                    "mensaje":    f"{item.get('nombre', tk)} entro en zona de compra "
                                  f"(target USD {entry_low}-{entry_high}, actual USD {precio:.2f}). "
                                  f"Tesis: {item.get('tesis', '')}",
                    "metricas":   {"precio": precio, "entry_low": entry_low, "entry_high": entry_high,
                                   "bucket": item.get("bucket", "")},
                    "sugerencia": f"Comprar USD {size[0]}-{size[1]}. Ticker Tier 1 alta conviccion.",
                })
            elif precio < entry_low * 0.9:
                # Below target — even better but might signal trouble
                alerts.append({
                    "categoria":  "watchlist_entry",
                    "severidad":  "alta",
                    "activo":     tk,
                    "titulo":     f"BELOW TARGET: {tk} a USD {precio:.2f}",
                    "mensaje":    f"{item.get('nombre', tk)} esta POR DEBAJO del entry target "
                                  f"(target USD {entry_low}-{entry_high}, actual USD {precio:.2f}). "
                                  f"Verificar que no haya catalyst negativo. "
                                  f"Tesis: {item.get('tesis', '')}",
                    "metricas":   {"precio": precio, "entry_low": entry_low, "entry_high": entry_high,
                                   "bucket": item.get("bucket", "")},
                    "sugerencia": f"Revisar noticias. Si tesis OK, oportunidad mayor: USD {size[0]}-{size[1]}.",
                })

    return alerts


# ── TIER 2 TRIGGER CHECKS ──────────────────────────────────
def check_tier2_triggers(watchlist_cfg: dict, metrics_map: dict) -> list:
    """Revisa triggers de Tier 2 (caida >10%, bajo USD X, etc.)."""
    alerts = []
    tier2 = watchlist_cfg.get("watchlist", {}).get("tier2", [])

    for item in tier2:
        tk = item.get("ticker")
        trigger = item.get("trigger", "")
        m = metrics_map.get(tk)
        if not tk or not m:
            continue

        triggered = False
        msg_extra = ""

        if "caida >10%" in trigger.lower():
            # Check 20d drawdown
            if m["pct_20d"] is not None and m["pct_20d"] <= -10:
                triggered = True
                msg_extra = f"Cayo {m['pct_20d']:.1f}% en 20d."
        elif "bajo usd" in trigger.lower():
            import re
            match = re.search(r"bajo usd\s*([\d.]+)", trigger.lower())
            if match:
                target = float(match.group(1))
                if m["precio_actual"] <= target:
                    triggered = True
                    msg_extra = f"Precio USD {m['precio_actual']:.2f} (bajo target USD {target})."

        if triggered:
            alerts.append({
                "categoria":  "watchlist_tier2",
                "severidad":  "media",
                "activo":     tk,
                "titulo":     f"TIER 2 TRIGGER: {tk}",
                "mensaje":    f"{item.get('nombre', tk)}: {msg_extra} "
                              f"Bucket: {item.get('bucket', '')}. "
                              f"Tesis: {item.get('tesis', '')}",
                "metricas":   {"precio": m["precio_actual"], "trigger": trigger,
                               "bucket": item.get("bucket", "")},
                "sugerencia": f"Oportunidad oportunistica. Evaluar entry.",
            })

    return alerts


# ── PENDING ACTIONS REMINDERS ───────────────────────────────
def check_pending_actions(watchlist_cfg: dict, metrics_map: dict) -> list:
    """Genera recordatorios para acciones pendientes de alta urgencia."""
    alerts = []
    pendientes = watchlist_cfg.get("acciones_pendientes", [])

    for item in pendientes:
        tk = item.get("ticker")
        urgencia = item.get("urgencia", "baja")
        if urgencia not in ("alta", "media"):
            continue  # Solo recordar urgentes

        m = metrics_map.get(tk, {})
        precio = m.get("precio_actual", 0) if m else 0
        precio_str = f" Precio actual: USD {precio:.2f}." if precio else ""

        sev = "alta" if urgencia == "alta" else "media"
        accion = item.get("accion", "?")
        monto = item.get("monto_usd")
        monto_str = f" USD {monto}" if monto else ""

        alerts.append({
            "categoria":  "accion_pendiente",
            "severidad":  sev,
            "activo":     tk,
            "titulo":     f"PENDIENTE: {accion} {tk}{monto_str}",
            "mensaje":    f"{item.get('nota', '')}.{precio_str}",
            "metricas":   {"accion": accion, "monto_usd": monto, "urgencia": urgencia,
                           "precio": precio},
            "sugerencia": f"Ejecutar {accion} de {tk}." if accion == "COMPRAR" else f"Revisar {tk}.",
        })

    return alerts


# ── SCORE COMPUESTO ─────────────────────────────────────────
def fetch_cross_signals() -> tuple:
    """Señales informacionales recientes para cruzar con las técnicas.
    → (insider_tickers: set, mention_counts: dict ticker→n)"""
    sb = get_client()
    insider_tickers = set()
    mention_counts = {}
    cutoff_ins = (date.today() - timedelta(days=14)).isoformat()
    cutoff_news = (date.today() - timedelta(days=7)).isoformat()
    try:
        r = (sb.table("portfolio_alerts").select("activo,categoria")
             .in_("categoria", ["insider_buy", "insider_cluster", "smart_money_13f"])
             .gte("fecha_alerta", cutoff_ins).execute())
        insider_tickers = {row["activo"] for row in r.data}
    except Exception:
        pass
    try:
        r = (sb.table("market_news").select("tickers_mencionados,relevancia_preliminar")
             .gte("fecha_noticia", cutoff_news)
             .gte("relevancia_preliminar", 40).execute())
        for row in r.data:
            for tk in (row.get("tickers_mencionados") or []):
                mention_counts[tk] = mention_counts.get(tk, 0) + 1
    except Exception:
        pass
    return insider_tickers, mention_counts


def compute_scores(alerts: list, insider_tickers: set, mention_counts: dict):
    """Score 0-100 por alerta: técnica × informacional × convicción.
    Se guarda en metricas.score y define el orden del reporte."""
    sev_base = {"critica": 40, "alta": 30, "media": 20, "baja": 12, "info": 8}
    conv_bonus = {"recurrente": 10, "tier1": 10, "cartera": 8, "tier2": 5, "tier3": 0}

    for a in alerts:
        m = a.get("metricas") or {}
        score = sev_base.get(a.get("severidad", "info"), 8)

        # Magnitud técnica: z-score del move
        z = None
        for k in ("z_5d", "z_20d", "z_60d"):
            if m.get(k) is not None:
                z = m[k] if z is None else min(z, m[k])
        if z is not None:
            score += min(15, abs(z) * 5)

        # RSI(2) extremo
        rsi2 = m.get("rsi2")
        if rsi2 is not None:
            if rsi2 < 5:
                score += 10
            elif rsi2 < 10:
                score += 5

        # Convicción
        score += conv_bonus.get(m.get("conviction", ""), 0)

        # Cross-signal informacional: insiders/13F comprando el mismo ticker
        tk = a.get("activo", "")
        if tk in insider_tickers and a["categoria"].startswith(("oportunidad", "watchlist")):
            score += 15
            a["mensaje"] = a.get("mensaje", "") + " ⚡ Cross-signal: insiders/smart money compraron recientemente."
        # Mención en newsletters curadas / noticias relevantes
        if mention_counts.get(tk, 0) >= 1 and a["categoria"].startswith(("oportunidad", "watchlist")):
            score += min(10, 5 * mention_counts[tk])

        m["score"] = int(min(100, score))
        a["metricas"] = m


# ── ENTRY TARGETS DINÁMICOS ─────────────────────────────────
def check_target_drift(watchlist_cfg: dict, metrics_map: dict) -> list:
    """Los entry targets fijados a mano envejecen. Sugiere recalibración
    cuando la banda técnica actual (soporte 60d ↔ SMA50) se alejó >12%
    del target del YAML. Corre solo los lunes para no spamear."""
    alerts = []
    for item in watchlist_cfg.get("watchlist", {}).get("tier1", []):
        tk = item.get("ticker")
        entry = item.get("entry_usd")
        m = metrics_map.get(tk)
        if not tk or not entry or not m:
            continue
        sma50 = m.get("sma50")
        low60 = m.get("low_60d")
        if not sma50 or not low60:
            continue
        sug_low = round(max(low60, sma50 * 0.85), 2)
        sug_high = round(sma50, 2)
        yaml_mid = (entry[0] + entry[1]) / 2
        sug_mid = (sug_low + sug_high) / 2
        drift_pct = (sug_mid / yaml_mid - 1) * 100
        if abs(drift_pct) > 12:
            alerts.append({
                "categoria":  "target_recalibrar",
                "severidad":  "info",
                "activo":     tk,
                "titulo":     f"RECALIBRAR TARGET: {tk} ({drift_pct:+.0f}% de drift)",
                "mensaje":    f"El entry target de {tk} en watchlist.yaml "
                              f"(USD {entry[0]}-{entry[1]}) quedó {abs(drift_pct):.0f}% "
                              f"{'bajo' if drift_pct > 0 else 'sobre'} la banda técnica actual "
                              f"(soporte 60d ↔ SMA50 = USD {sug_low}-{sug_high}). "
                              f"Precio actual: USD {m['precio_actual']:.2f}.",
                "metricas":   {"target_yaml": entry, "target_sugerido": [sug_low, sug_high],
                               "drift_pct": round(drift_pct, 1), "precio": m["precio_actual"]},
                "sugerencia": f"Actualizar entry_usd de {tk} a ~[{sug_low}, {sug_high}] en "
                              f"watchlist.yaml si la tesis sigue igual.",
            })
    return alerts


# ── SAVE ────────────────────────────────────────────────────
# Categorías que ESTE módulo posee: se desactivan TODAS antes de insertar,
# para que las señales que dejaron de disparar no queden activas para siempre.
OWNED_CATEGORIES = ["oportunidad_dip", "oportunidad_rsi2", "watchlist_entry",
                    "watchlist_tier2", "accion_pendiente", "momentum_warning",
                    "target_recalibrar", "market_regime"]


def save_alerts(alerts: list) -> dict:
    sb = get_client()
    ins = dup = err = 0

    # Desactivar TODAS las alertas previas de las categorías propias
    # (no solo las que se re-insertan — evita señales zombie)
    for cat in OWNED_CATEGORIES:
        try:
            sb.table("portfolio_alerts").update({"activo_alerta": False}) \
              .eq("activo_alerta", True) \
              .eq("categoria", cat) \
              .execute()
        except Exception:
            pass

    if not alerts:
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}

    for a in alerts:
        try:
            sb.table("portfolio_alerts").insert(a).execute()
            ins += 1
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg:
                try:
                    sb.table("portfolio_alerts").update({
                        "activo_alerta": True,
                        "mensaje": a.get("mensaje"),
                        "metricas": a.get("metricas"),
                        "sugerencia": a.get("sugerencia"),
                        "severidad": a.get("severidad"),
                        "titulo": a.get("titulo"),
                    }).eq("categoria", a["categoria"]).eq("activo", a["activo"]).execute()
                    dup += 1
                except Exception:
                    err += 1
            else:
                err += 1
                if err <= 3:
                    print(f"  {a['activo']}: {str(e)[:120]}")
    return {"insertadas": ins, "duplicadas": dup, "errores": err}


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No escribe a Supabase")
    parser.add_argument("--ticker", default=None, help="Solo un ticker especifico")
    parser.add_argument("--targets", action="store_true",
                        help="Forzar chequeo de target drift (normal: solo lunes)")
    args = parser.parse_args()

    print("=" * 60)
    print("OPPORTUNITY DETECTOR v2 — Watchlist + Cartera + Connors")
    print("=" * 60)

    rules = load_rules()
    wl_cfg = load_watchlist_config()
    profile = load_profile()
    df_cart = load_cartera()

    # ── Régimen de mercado (modula TODAS las señales) ────────
    print("Clasificando régimen de mercado (FRED + SPY + VIX)...")
    try:
        from intelligence.market_regime import compute_market_regime, regime_label
        regime = compute_market_regime()
        regime_txt = regime_label(regime)
        print(f"  {regime_txt}")
    except Exception as e:
        regime = {"regimen": "neutral", "puntos_estres": 0, "senales_disponibles": 0, "senales": {}}
        regime_txt = "Régimen no disponible (error de datos)"
        print(f"  {str(e)[:80]}")

    # Contexto para sizing por riesgo
    portfolio_intl_usd = 0
    if not df_cart.empty:
        intl = df_cart[df_cart["mercado"] == "internacional"]
        portfolio_intl_usd = float(intl["valor_usd"].sum())
    sizing_ctx = {
        "sizing": profile.get("sizing", {}),
        "portfolio_usd": portfolio_intl_usd,
        "regimen": regime["regimen"],
    }
    # Tickers nivel_riesgo=alto (perfil por verticales, no bucket único) —
    # eximidos del chequeo de margen en check_fundamentals (son pre-profit
    # por definición en su etapa, exigirles margen positivo no tiene sentido)
    especulativos = {
        tk for vert in profile.get("verticales", {}).values()
        for tk, info in vert.get("tickers", {}).items()
        if info.get("nivel_riesgo") == "alto"
    }

    # Build exclusion list from watchlist.yaml
    excluded = set(wl_cfg.get("etfs_core_no_alert", []))
    gf = rules.get("global_filters", {})

    # ── Build ticker universe ────────────────────────────────
    # conviction levels: "cartera" | "recurrente" | "tier1" | "tier2" | "tier3"
    #   cartera/recurrente/tier1 → COMPRAR con monto
    #   tier2 → EVALUAR COMPRA (oportunístico)
    #   tier3 → EVALUAR solamente (seguimiento)

    # Pre-build sets for conviction lookup
    recurrente_tickers = {r["ticker"] for r in wl_cfg.get("recurrente", []) if r.get("ticker")}
    tier1_tickers = {i["ticker"] for i in wl_cfg.get("watchlist", {}).get("tier1", []) if i.get("ticker")}
    tier2_tickers = {i["ticker"] for i in wl_cfg.get("watchlist", {}).get("tier2", []) if i.get("ticker")}
    tier3_tickers = {i["ticker"] for i in wl_cfg.get("watchlist", {}).get("tier3", []) if i.get("ticker")}

    def _get_conviction(tk: str) -> str:
        """Devuelve nivel de convicción más alto que aplique."""
        if tk in recurrente_tickers:
            return "recurrente"
        if tk in tier1_tickers:
            return "tier1"
        if tk in tier2_tickers:
            return "tier2"
        if tk in tier3_tickers:
            return "tier3"
        return "cartera"  # posición en cartera sin categoría especial

    # 1. Cartera positions (above minimum value)
    tickers_to_eval = {}  # ticker -> {mercado, tesis, bucket, conviction}
    if not df_cart.empty:
        min_val = gf.get("min_position_or_watchlist_usd", 100) * USD_CLP
        for _, row in df_cart.iterrows():
            tk = row.get("ticker")
            if not tk or tk == "PORTFOLIO_CL" or tk in excluded:
                continue
            if row.get("valor_clp", 0) < min_val:
                continue
            # Find tesis from recurrente plan
            tesis = ""
            bucket = ""
            for r in wl_cfg.get("recurrente", []):
                if r["ticker"] == tk:
                    tesis = r.get("tesis", "")
                    bucket = r.get("bucket", "")
                    break
            tickers_to_eval[tk] = {
                "mercado": row.get("mercado", "internacional"),
                "tesis": tesis,
                "bucket": bucket,
                "conviction": _get_conviction(tk),
            }

    # 2. Watchlist tickers (all tiers)
    for tier_key in ["tier1", "tier2", "tier3"]:
        for item in wl_cfg.get("watchlist", {}).get(tier_key, []):
            tk = item.get("ticker")
            if tk and tk not in excluded and tk not in tickers_to_eval:
                tickers_to_eval[tk] = {
                    "mercado": "internacional",
                    "tesis": item.get("tesis", ""),
                    "bucket": item.get("bucket", ""),
                    "conviction": tier_key,
                }

    # 3. Acciones pendientes (alta convicción, son explícitamente pedidas)
    for item in wl_cfg.get("acciones_pendientes", []):
        tk = item.get("ticker")
        if tk and tk not in excluded and tk not in tickers_to_eval:
            tickers_to_eval[tk] = {
                "mercado": "internacional",
                "tesis": item.get("nota", ""),
                "bucket": "",
                "conviction": "cartera",
            }

    if args.ticker:
        if args.ticker in tickers_to_eval:
            tickers_to_eval = {args.ticker: tickers_to_eval[args.ticker]}
        else:
            tickers_to_eval = {args.ticker: {"mercado": "internacional", "tesis": "", "bucket": ""}}

    cart_count = len([t for t in tickers_to_eval if t in set(df_cart["ticker"].tolist())] if not df_cart.empty else [])
    wl_count = len(tickers_to_eval) - cart_count

    print(f"\n{len(tickers_to_eval)} tickers a evaluar "
          f"({cart_count} cartera + {wl_count} watchlist) "
          f"| {len(excluded)} excluidos (ETFs core)")

    # ── Download prices ──────────────────────────────────────
    yf_map = {}
    for tk, info in tickers_to_eval.items():
        yf_map[tk] = yf_ticker_for(tk, info["mercado"])

    yf_unique = list(set(yf_map.values()))
    print(f"Descargando historico 1y de {len(yf_unique)} tickers...")
    raw = fetch_history(yf_unique, period="1y")

    if raw.empty:
        print("yfinance retorno vacio.")
        return

    # ── Calculate metrics for all tickers ────────────────────
    metrics_map = {}  # ticker -> metrics dict
    skipped = 0
    for tk, info in tickers_to_eval.items():
        yf_tk = yf_map.get(tk)
        if not yf_tk:
            skipped += 1
            continue
        close, volume = get_ticker_series(raw, yf_tk)
        if close is None:
            skipped += 1
            continue
        m = calc_metrics(close, volume)
        if m:
            metrics_map[tk] = m
        else:
            skipped += 1

    print(f"Metricas calculadas: {len(metrics_map)} tickers ({skipped} sin data)\n")

    # ── Run all checks ───────────────────────────────────────
    all_alerts = []

    # 1. Connors DIP rules on all tickers (con sizing por riesgo + régimen)
    print("Connors DIP rules...")
    for tk, m in metrics_map.items():
        info = tickers_to_eval.get(tk, {})
        alerts = evaluate_connors_rules(
            tk, m, rules,
            tesis=info.get("tesis", ""),
            bucket=info.get("bucket", ""),
            conviction=info.get("conviction", "cartera"),
            ctx=sizing_ctx,
        )
        all_alerts.extend(alerts)
    print(f"  {len(all_alerts)} alertas DIP/momentum")

    # 1b. Gate fundamental: dips en negocios deteriorándose se degradan
    #     (solo tickers que YA alertaron — pocas llamadas yfinance)
    dip_tickers = {a["activo"] for a in all_alerts
                   if a["categoria"] in ("oportunidad_dip", "oportunidad_rsi2")}
    if dip_tickers:
        print(f"Gate fundamental ({len(dip_tickers)} tickers con dip)...")
        degradadas = 0
        fund_cache = {}
        for tk in dip_tickers:
            fund_cache[tk] = check_fundamentals(tk, especulativos)
        for a in all_alerts:
            if a["categoria"] not in ("oportunidad_dip", "oportunidad_rsi2"):
                continue
            f = fund_cache.get(a["activo"], {})
            a["metricas"]["fundamentales"] = f.get("estado", "sin_datos")
            if f.get("estado") == "debil":
                notas = ", ".join(f.get("notas", []))
                sev_down = {"critica": "alta", "alta": "media", "media": "info"}
                a["severidad"] = sev_down.get(a["severidad"], "info")
                a["sugerencia"] = (f"⚠️ FUNDAMENTALES DÉBILES ({notas}): NO promediar "
                                   f"sin revisar la tesis primero. " + a.get("sugerencia", ""))
                degradadas += 1
        print(f"  {degradadas} alertas degradadas por fundamentales débiles")

    # 2. Watchlist entry targets (Tier 1)
    print("Entry targets (Tier 1)...")
    entry_alerts = check_entry_targets(wl_cfg, metrics_map)
    all_alerts.extend(entry_alerts)
    print(f"  {len(entry_alerts)} entry targets")

    # 3. Tier 2 triggers
    print("Tier 2 triggers...")
    t2_alerts = check_tier2_triggers(wl_cfg, metrics_map)
    all_alerts.extend(t2_alerts)
    print(f"  {len(t2_alerts)} tier 2 triggers")

    # 4. Pending actions
    print("Acciones pendientes...")
    pending_alerts = check_pending_actions(wl_cfg, metrics_map)
    all_alerts.extend(pending_alerts)
    print(f"  {len(pending_alerts)} recordatorios")

    # 5. Entry target drift (solo lunes, targets manuales envejecen)
    if date.today().weekday() == 0 or args.targets:
        print("Target drift check (tier 1)...")
        drift_alerts = check_target_drift(wl_cfg, metrics_map)
        all_alerts.extend(drift_alerts)
        print(f"  {len(drift_alerts)} targets a recalibrar")

    # ── Coherencia con acciones pendientes: un ticker con VENDER
    #    pendiente NUNCA debe generar sugerencias de COMPRA ─────
    vender_tickers = {i["ticker"] for i in wl_cfg.get("acciones_pendientes", [])
                      if i.get("accion") == "VENDER" and i.get("ticker")}
    if vender_tickers:
        antes = len(all_alerts)
        all_alerts = [a for a in all_alerts
                      if not (a["activo"] in vender_tickers and
                              a["categoria"] in ("oportunidad_dip", "oportunidad_rsi2",
                                                 "watchlist_entry", "watchlist_tier2"))]
        if antes != len(all_alerts):
            print(f"  Filtradas {antes - len(all_alerts)} alertas de compra en tickers "
                  f"con VENDER pendiente: {sorted(vender_tickers)}")

    # ── Score compuesto: técnica × informacional × convicción ─
    print("Score compuesto (cross-signals: insiders + newsletters)...")
    insider_tks, mentions = fetch_cross_signals()
    compute_scores(all_alerts, insider_tks, mentions)

    # ── Sort by score, cap para no spamear ──────────────────
    all_alerts.sort(key=lambda a: -(a.get("metricas", {}).get("score", 0)))
    max_alerts = gf.get("max_alerts_per_run", 15)
    if len(all_alerts) > max_alerts:
        print(f"  Cap: {len(all_alerts)} → top {max_alerts} por score")
        all_alerts = all_alerts[:max_alerts]

    # Alerta de régimen (informativa, exenta del cap — encabeza el email)
    all_alerts.append({
        "categoria": "market_regime", "severidad": "info", "activo": "MARKET",
        "titulo": regime_txt[:120],
        "mensaje": regime_txt,
        "metricas": {"regimen": regime["regimen"], "puntos": regime["puntos_estres"],
                     "disponibles": regime["senales_disponibles"], "score": 0},
        "sugerencia": {
            "risk_on": "Señales de compra operan normal.",
            "neutral": "Cautela moderada: sizing estándar, confirmar tesis antes de agregar.",
            "risk_off": "Sizing reducido 50% automático. Priorizar core/DCA, no promediar especulativas.",
        }[regime["regimen"]],
    })

    print(f"\nTotal alertas: {len(all_alerts)}")
    if all_alerts:
        from collections import Counter
        by_cat = Counter(a["categoria"] for a in all_alerts)
        for cat, n in by_cat.most_common():
            print(f"   {cat}: {n}")

    if args.dry_run:
        print("\nDRY RUN — no se guardo nada")
        for a in all_alerts[:15]:
            score = a.get("metricas", {}).get("score", 0)
            print(f"  [{score:>3d}] [{a['severidad'].upper():8s}] {a['titulo']}")
        return

    result = save_alerts(all_alerts)
    print(f"\nInsertadas: {result['insertadas']}")
    print(f"Actualizadas: {result['duplicadas']}")
    print(f"Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
