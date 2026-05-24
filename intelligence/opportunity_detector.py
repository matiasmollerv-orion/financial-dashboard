# ============================================================
# OPPORTUNITY DETECTOR — Reglas profesionales pre-comprometidas
#
# Aplica las reglas de intelligence/config/rules.yaml sobre cada
# posición de la cartera (y watchlist):
#
#   🟡 DIP CHICO     -10% en 5d + filtros
#   🟠 DIP MEDIO     -15% en 20d + filtros
#   🔴 DIP GRANDE    -25% en 60d
#   🚨 BEAR CRASH    -40% desde ATH (1y)
#   ⚠️ MOMENTUM      +30% en 20d → considerar trim
#   📈 NEAR ATH      <5% del ATH → solo info
#
# El sistema NO compra — solo alerta. Guarda en portfolio_alerts
# con categoria='oportunidad_dip' o 'momentum_warning'.
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


# ── HELPERS ──────────────────────────────────────────────────
def load_rules() -> dict:
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cartera() -> pd.DataFrame:
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
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


def fetch_history(yf_tickers: list, period: str = "1y") -> pd.DataFrame:
    """Descarga precios + volumen históricos. Retorna multi-index (Close, Volume)."""
    try:
        import yfinance as yf
        raw = yf.download(
            yf_tickers, period=period, interval="1d",
            auto_adjust=True, progress=False, group_by="ticker",
        )
        return raw
    except Exception as e:
        print(f"  ⚠️ yfinance error: {e}")
        return pd.DataFrame()


def get_ticker_series(raw, yf_tk):
    """Extrae Close + Volume series para un ticker del MultiIndex raw."""
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


# ── EVALUADORES DE REGLAS ────────────────────────────────────
def calc_metrics(close: pd.Series, volume: pd.Series) -> dict:
    """Calcula todas las métricas necesarias para evaluar reglas."""
    if close is None or len(close.dropna()) < 20:
        return None
    close = close.dropna()
    metrics = {
        "precio_actual": float(close.iloc[-1]),
        "precio_5d_atras":   float(close.iloc[-min(6, len(close))]) if len(close) >= 6 else None,
        "precio_20d_atras":  float(close.iloc[-min(21, len(close))]) if len(close) >= 21 else None,
        "precio_60d_atras":  float(close.iloc[-min(61, len(close))]) if len(close) >= 61 else None,
        "ath_252d":          float(close.tail(252).max()) if len(close) > 0 else None,
        "high_20d":          float(close.tail(20).max()),
    }
    # Cambios porcentuales
    p_now = metrics["precio_actual"]
    metrics["pct_5d"]   = ((p_now / metrics["precio_5d_atras"]  - 1) * 100) if metrics["precio_5d_atras"]  else None
    metrics["pct_20d"]  = ((p_now / metrics["precio_20d_atras"] - 1) * 100) if metrics["precio_20d_atras"] else None
    metrics["pct_60d"]  = ((p_now / metrics["precio_60d_atras"] - 1) * 100) if metrics["precio_60d_atras"] else None
    metrics["pct_from_ath"] = ((p_now / metrics["ath_252d"] - 1) * 100) if metrics["ath_252d"] else None

    # SMA200
    if len(close) >= 200:
        sma200 = float(close.tail(200).mean())
        metrics["sma200"] = sma200
        metrics["above_sma200"] = p_now > sma200
    else:
        metrics["sma200"] = None
        metrics["above_sma200"] = None  # unknown

    # Volume ratio (últimos 5d vs promedio 60d)
    if volume is not None and len(volume.dropna()) >= 60:
        vol_recent = float(volume.tail(5).mean())
        vol_avg    = float(volume.tail(60).mean())
        metrics["volume_ratio"] = (vol_recent / vol_avg) if vol_avg > 0 else None
    else:
        metrics["volume_ratio"] = None

    return metrics


def evaluate_dip_rules(ticker: str, mercado: str, m: dict, rules: dict) -> list:
    """Aplica reglas de DIP y MOMENTUM. Retorna list[dict] de alertas."""
    alerts = []
    dips = rules.get("dips", {})
    momentum = rules.get("momentum", {})

    # 1. DIP CHICO
    rule = dips.get("small_dip", {})
    if m["pct_5d"] is not None and m["pct_5d"] <= rule["threshold_pct"]:
        ok = True
        if rule.get("require_above_sma200") and m["above_sma200"] is False:
            ok = False
        if rule.get("require_volume_ratio") and m["volume_ratio"] is not None:
            if m["volume_ratio"] < rule["require_volume_ratio"]:
                ok = False
        if ok:
            sma_note = "Sobre SMA200 ✓ " if m.get('above_sma200') else ""
            vol_note = f"Vol {m['volume_ratio']:.1f}x" if m.get('volume_ratio') else ""
            alerts.append({
                "categoria":  "oportunidad_dip",
                "severidad":  rule["severidad"],
                "activo":     ticker,
                "titulo":     f"{rule['label']} en {ticker}",
                "mensaje":    f"{ticker} cayó {m['pct_5d']:.1f}% en 5 días. "
                              f"Precio: USD {m['precio_actual']:.2f}. {sma_note}{vol_note}",
                "metricas":   {"pct_5d": round(m["pct_5d"], 2), "precio": m["precio_actual"],
                               "volume_ratio": m.get("volume_ratio"), "above_sma200": m.get("above_sma200")},
                "sugerencia": f"Considerar compra USD {rule['accion_min_usd']}-{rule['accion_max_usd']}. "
                              f"Verificar primero que no haya catalyst negativo en noticias.",
            })

    # 2. DIP MEDIO
    rule = dips.get("medium_dip", {})
    if m["pct_20d"] is not None and m["pct_20d"] <= rule["threshold_pct"]:
        ok = True
        if rule.get("require_above_sma200") and m["above_sma200"] is False:
            ok = False
        if ok:
            alerts.append({
                "categoria":  "oportunidad_dip",
                "severidad":  rule["severidad"],
                "activo":     ticker,
                "titulo":     f"{rule['label']} en {ticker}",
                "mensaje":    f"{ticker} cayó {m['pct_20d']:.1f}% en 20 días. "
                              f"Precio actual: USD {m['precio_actual']:.2f}.",
                "metricas":   {"pct_20d": round(m["pct_20d"], 2), "precio": m["precio_actual"],
                               "above_sma200": m.get("above_sma200")},
                "sugerencia": f"Compra puntual USD {rule['accion_min_usd']}-{rule['accion_max_usd']} "
                              f"si la tesis sigue intacta. Revisar earnings recientes.",
            })

    # 3. DIP GRANDE
    rule = dips.get("large_dip", {})
    if m["pct_60d"] is not None and m["pct_60d"] <= rule["threshold_pct"]:
        alerts.append({
            "categoria":  "oportunidad_dip",
            "severidad":  rule["severidad"],
            "activo":     ticker,
            "titulo":     f"{rule['label']} en {ticker}",
            "mensaje":    f"{ticker} cayó {m['pct_60d']:.1f}% en 60 días. "
                          f"Precio: USD {m['precio_actual']:.2f}.",
            "metricas":   {"pct_60d": round(m["pct_60d"], 2), "precio": m["precio_actual"]},
            "sugerencia": f"Oportunidad agresiva USD {rule['accion_min_usd']}-{rule['accion_max_usd']}. "
                          f"Si fundamentales OK, promediar fuerte.",
        })

    # 4. BEAR CRASH
    rule = dips.get("bear_crash", {})
    if m["pct_from_ath"] is not None and m["pct_from_ath"] <= rule["threshold_pct"]:
        alerts.append({
            "categoria":  "oportunidad_dip",
            "severidad":  rule["severidad"],
            "activo":     ticker,
            "titulo":     f"{rule['label']} en {ticker}",
            "mensaje":    f"{ticker} bajó {m['pct_from_ath']:.1f}% desde all-time-high. "
                          f"Precio: USD {m['precio_actual']:.2f} vs ATH USD {m['ath_252d']:.2f}.",
            "metricas":   {"pct_from_ath": round(m["pct_from_ath"], 2),
                           "precio": m["precio_actual"], "ath": m["ath_252d"]},
            "sugerencia": f"⚠️ MANUAL REVIEW: verificar que tesis siga intacta. "
                          f"Si OK, compra event-driven USD {rule['accion_min_usd']}-{rule['accion_max_usd']}.",
        })

    # 5. MOMENTUM EXTREMO (subió mucho)
    rule = momentum.get("extreme_rally", {})
    if m["pct_20d"] is not None and m["pct_20d"] >= rule["threshold_pct"]:
        alerts.append({
            "categoria":  "momentum_warning",
            "severidad":  rule["severidad"],
            "activo":     ticker,
            "titulo":     f"{rule['label']} en {ticker}",
            "mensaje":    f"{ticker} subió +{m['pct_20d']:.1f}% en 20 días. "
                          f"Precio: USD {m['precio_actual']:.2f}.",
            "metricas":   {"pct_20d": round(m["pct_20d"], 2), "precio": m["precio_actual"]},
            "sugerencia": rule["descripcion"],
        })

    # 6. NEAR ATH (informativo)
    rule = momentum.get("near_ath", {})
    if m["pct_from_ath"] is not None and abs(m["pct_from_ath"]) <= rule["distance_from_ath_pct"]:
        alerts.append({
            "categoria":  "momentum_warning",
            "severidad":  rule["severidad"],
            "activo":     ticker,
            "titulo":     f"{rule['label']} {ticker} ({m['pct_from_ath']:.1f}% del ATH)",
            "mensaje":    f"{ticker} está a {abs(m['pct_from_ath']):.1f}% del all-time-high. "
                          f"Precio: USD {m['precio_actual']:.2f} · ATH: USD {m['ath_252d']:.2f}.",
            "metricas":   {"pct_from_ath": round(m["pct_from_ath"], 2), "precio": m["precio_actual"]},
            "sugerencia": rule["descripcion"],
        })

    return alerts


# ── SAVE (con auto-dedupe) ───────────────────────────────────
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
                    print(f"  ❌ {a['activo']}: {str(e)[:120]}")
    return {"insertadas": ins, "duplicadas": dup, "errores": err}


# ── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No escribe a Supabase")
    parser.add_argument("--ticker", default=None, help="Solo un ticker específico")
    args = parser.parse_args()

    print("=" * 60)
    print("🎯 OPPORTUNITY DETECTOR — Aplicando reglas pre-comprometidas")
    print("=" * 60)

    rules = load_rules()
    df_cart = load_cartera()
    if df_cart.empty:
        print("⚠️ Cartera vacía.")
        return

    gf = rules["global_filters"]
    excluded = set(gf.get("exclude_tickers", []))

    # Filtrar:
    df_eval = df_cart[
        (~df_cart["ticker"].isin(excluded)) &
        (df_cart["valor_clp"].fillna(0) >= gf["min_position_or_watchlist_usd"] * USD_CLP)
    ].copy()

    # Agregar watchlist (sin posición pero a monitorear)
    watchlist = rules.get("watchlist", [])
    cart_tickers = set(df_eval["ticker"].dropna().tolist())
    extra = [w for w in watchlist if w not in cart_tickers]
    for w in extra:
        df_eval = pd.concat([df_eval, pd.DataFrame([{
            "ticker": w, "mercado": "internacional", "moneda": "USD",
            "cantidad": 0, "valor_clp": 0,
        }])], ignore_index=True)

    if args.ticker:
        df_eval = df_eval[df_eval["ticker"] == args.ticker]

    print(f"\n📊 {len(df_eval)} tickers a evaluar "
          f"({len(df_eval) - len(extra)} cartera + {len(extra)} watchlist) "
          f"· {len(excluded)} excluidos (ETFs core)")

    # Construir map ticker → yf_ticker
    yf_map = {}
    for _, row in df_eval.iterrows():
        tk = row["ticker"]
        if not tk or tk == "PORTFOLIO_CL":
            continue
        yf_map[tk] = yf_ticker_for(tk, row.get("mercado", "internacional"))

    if not yf_map:
        print("Sin tickers válidos para evaluar.")
        return

    yf_unique = list(set(yf_map.values()))
    print(f"📡 Descargando histórico 1y de {len(yf_unique)} tickers…")
    raw = fetch_history(yf_unique, period="1y")

    if raw.empty:
        print("❌ yfinance retornó vacío.")
        return

    # Evaluar cada ticker
    all_alerts = []
    skipped = 0
    for _, row in df_eval.iterrows():
        tk = row["ticker"]
        if tk not in yf_map:
            continue
        yf_tk = yf_map[tk]
        close, volume = get_ticker_series(raw, yf_tk)
        if close is None:
            skipped += 1
            continue
        metrics = calc_metrics(close, volume)
        if not metrics:
            skipped += 1
            continue
        alerts = evaluate_dip_rules(tk, row.get("mercado", "internacional"), metrics, rules)
        all_alerts.extend(alerts)

    # Limit
    max_alerts = gf.get("max_alerts_per_run", 50)
    sev_order = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "info": 4}
    all_alerts.sort(key=lambda a: sev_order.get(a.get("severidad", "info"), 99))
    if len(all_alerts) > max_alerts:
        print(f"⚠️ {len(all_alerts)} alertas detectadas, truncando a max_alerts_per_run={max_alerts}")
        all_alerts = all_alerts[:max_alerts]

    print(f"\n📋 Total alertas: {len(all_alerts)} ({skipped} tickers sin data suficiente)")
    if all_alerts:
        from collections import Counter
        by_label = Counter(a["titulo"].split(" en ")[0] for a in all_alerts)
        for label, n in by_label.most_common():
            print(f"   {label}: {n}")

    if args.dry_run:
        print("\n⚠️ DRY RUN — no se guardó nada")
        return

    result = save_alerts(all_alerts)
    print(f"\n✅ Insertadas: {result['insertadas']}")
    print(f"♻️ Actualizadas: {result['duplicadas']}")
    print(f"❌ Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
