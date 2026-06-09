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


USD_CLP = 901.76
RULES_PATH = Path(__file__).parent / "config" / "rules.yaml"
WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"


# ── LOADERS ─────────────────────────────────────────────────
def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_watchlist_config() -> dict:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
        return f"{ticker}.SN"
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

    if volume is not None and len(volume.dropna()) >= 60:
        vol_recent = float(volume.tail(5).mean())
        vol_avg    = float(volume.tail(60).mean())
        m["volume_ratio"] = (vol_recent / vol_avg) if vol_avg > 0 else None
    else:
        m["volume_ratio"] = None

    return m


# ── CONNORS DIP RULES ──────────────────────────────────────
def evaluate_connors_rules(ticker: str, m: dict, rules: dict,
                           tesis: str = "", bucket: str = "",
                           conviction: str = "cartera") -> list:
    """Aplica reglas Connors sobre un ticker. Retorna list[dict] de alertas.

    conviction: "cartera" | "recurrente" | "tier1" | "tier2" | "tier3"
      - cartera/recurrente/tier1: sugerencia = COMPRAR con monto
      - tier2: sugerencia = EVALUAR COMPRA (oportunístico)
      - tier3: sugerencia = EVALUAR solamente (seguimiento, sin acción)
    """
    alerts = []
    dips = rules.get("dips", {})
    momentum = rules.get("momentum", {})
    ctx = f" [{bucket}]" if bucket else ""
    tesis_note = f" Tesis: {tesis}" if tesis else ""

    # Ajustar sugerencia y severidad según nivel de convicción
    is_actionable = conviction in ("cartera", "recurrente", "tier1")
    is_tier2 = conviction == "tier2"
    # tier3 = solo evaluar

    def _sugerencia_dip(rule_name, rule_cfg):
        lo = rule_cfg.get("accion_min_usd", 150)
        hi = rule_cfg.get("accion_max_usd", 250)
        if is_actionable:
            if rule_name == "small_dip":
                return f"Considerar compra USD {lo}-{hi}."
            elif rule_name == "medium_dip":
                return f"Compra puntual USD {lo}-{hi} si tesis intacta."
            elif rule_name == "large_dip":
                return f"Oportunidad agresiva USD {lo}-{hi}."
            elif rule_name == "bear_crash":
                return f"MANUAL REVIEW. Si tesis viva, compra USD {lo}-{hi}."
        elif is_tier2:
            return f"Evaluar compra oportunística. Entry si tesis OK."
        else:  # tier3
            return f"Solo seguimiento. Evaluar si tesis mejora para subir a Tier 2."

    def _severidad(base_sev):
        """Tier 3 baja severidad; Tier 2 mantiene; cartera/recurrente/tier1 normal."""
        if conviction == "tier3":
            return "info" if base_sev == "media" else "media"
        return base_sev

    # 1. DIP CHICO (-10% en 5d)
    rule = dips.get("small_dip", {})
    if m["pct_5d"] is not None and m["pct_5d"] <= rule.get("threshold_pct", -10):
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
                "mensaje":    f"{ticker} cayo {m['pct_5d']:.1f}% en 5d. "
                              f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
                "metricas":   {"pct_5d": round(m["pct_5d"], 2), "precio": m["precio_actual"],
                               "bucket": bucket, "rule": "small_dip", "conviction": conviction},
                "sugerencia": _sugerencia_dip("small_dip", rule),
            })

    # 2. DIP MEDIO (-15% en 20d)
    rule = dips.get("medium_dip", {})
    if m["pct_20d"] is not None and m["pct_20d"] <= rule.get("threshold_pct", -15):
        ok = True
        if rule.get("require_above_sma200") and m["above_sma200"] is False:
            ok = False
        if ok:
            alerts.append({
                "categoria":  "oportunidad_dip",
                "severidad":  _severidad("alta"),
                "activo":     ticker,
                "titulo":     f"DIP MEDIO en {ticker}{ctx}",
                "mensaje":    f"{ticker} cayo {m['pct_20d']:.1f}% en 20d. "
                              f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
                "metricas":   {"pct_20d": round(m["pct_20d"], 2), "precio": m["precio_actual"],
                               "bucket": bucket, "rule": "medium_dip", "conviction": conviction},
                "sugerencia": _sugerencia_dip("medium_dip", rule),
            })

    # 3. DIP GRANDE (-25% en 60d)
    rule = dips.get("large_dip", {})
    if m["pct_60d"] is not None and m["pct_60d"] <= rule.get("threshold_pct", -25):
        alerts.append({
            "categoria":  "oportunidad_dip",
            "severidad":  _severidad("alta"),
            "activo":     ticker,
            "titulo":     f"DIP GRANDE en {ticker}{ctx}",
            "mensaje":    f"{ticker} cayo {m['pct_60d']:.1f}% en 60d. "
                          f"Precio: USD {m['precio_actual']:.2f}.{tesis_note}",
            "metricas":   {"pct_60d": round(m["pct_60d"], 2), "precio": m["precio_actual"],
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
                           "bucket": bucket, "rule": "extreme_rally", "conviction": conviction},
            "sugerencia": "NO comprar. Evaluar trim parcial 25-30%.",
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


# ── SAVE ────────────────────────────────────────────────────
def save_alerts(alerts: list) -> dict:
    if not alerts:
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}

    sb = get_client()
    ins = dup = err = 0

    # Desactivar previas con misma (categoria, activo)
    pairs = set((a["categoria"], a["activo"]) for a in alerts)
    for cat, activo in pairs:
        try:
            sb.table("portfolio_alerts").update({"activo_alerta": False}) \
              .eq("activo_alerta", True) \
              .eq("categoria", cat) \
              .eq("activo", activo) \
              .execute()
        except Exception:
            pass

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
    args = parser.parse_args()

    print("=" * 60)
    print("OPPORTUNITY DETECTOR v2 — Watchlist + Cartera + Connors")
    print("=" * 60)

    rules = load_rules()
    wl_cfg = load_watchlist_config()
    df_cart = load_cartera()

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

    # 1. Connors DIP rules on all tickers
    print("Connors DIP rules...")
    for tk, m in metrics_map.items():
        info = tickers_to_eval.get(tk, {})
        alerts = evaluate_connors_rules(
            tk, m, rules,
            tesis=info.get("tesis", ""),
            bucket=info.get("bucket", ""),
            conviction=info.get("conviction", "cartera"),
        )
        all_alerts.extend(alerts)
    print(f"  {len(all_alerts)} alertas DIP/momentum")

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

    # ── Sort by priority ─────────────────────────────────────
    sev_order = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "info": 4}
    all_alerts.sort(key=lambda a: sev_order.get(a.get("severidad", "info"), 99))

    print(f"\nTotal alertas: {len(all_alerts)}")
    if all_alerts:
        from collections import Counter
        by_cat = Counter(a["categoria"] for a in all_alerts)
        for cat, n in by_cat.most_common():
            print(f"   {cat}: {n}")

    if args.dry_run:
        print("\nDRY RUN — no se guardo nada")
        for a in all_alerts[:10]:
            print(f"  [{a['severidad'].upper():8s}] {a['titulo']}")
        return

    result = save_alerts(all_alerts)
    print(f"\nInsertadas: {result['insertadas']}")
    print(f"Actualizadas: {result['duplicadas']}")
    print(f"Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
