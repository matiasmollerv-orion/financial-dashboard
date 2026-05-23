# ============================================================
# PORTFOLIO HEALTH MONITOR
# Análisis independiente de la cartera: detecta riesgos sin
# depender de noticias externas.
#
# Uso: python -m intelligence.portfolio_health
# ============================================================

import sys
from datetime import datetime, timezone
from typing import Optional
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import numpy as np
import pandas as pd

from database.supabase_client import get_client


USD_CLP = 901.76  # consistente con dashboard/utils.py

# Umbrales (configurables)
THRESHOLDS = {
    "concentracion_ticker_pct":   20.0,   # 1 ticker > 20% cartera → alerta
    "concentracion_sector_pct":   40.0,
    "concentracion_pais_pct":     50.0,
    "pe_caro":                    30.0,
    "pe_alarma":                  40.0,
    "drawdown_alerta_pct":       -15.0,
    "drawdown_critico_pct":      -25.0,
    "stale_meses":                6,
    "crypto_max_pct":             15.0,
    "small_cap_chile_max_pct":    5.0,
}


# ── LOADERS ──────────────────────────────────────────────────
def load_portfolio() -> pd.DataFrame:
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return df

    for col in ["precio_compra", "precio_actual", "cantidad"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["valor_usd"]    = df["cantidad"] * df["precio_actual"]
    df["costo_usd"]    = df["cantidad"] * df["precio_compra"]
    if "moneda" not in df.columns:
        df["moneda"] = "USD"
    df["valor_clp"]    = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP,
        axis=1
    )
    df["costo_clp"]    = df.apply(
        lambda r: r["costo_usd"] if r.get("moneda") == "CLP" else r["costo_usd"] * USD_CLP,
        axis=1
    )
    df["ganancia_clp"] = df["valor_clp"] - df["costo_clp"]
    costo_safe = df["costo_clp"].where(df["costo_clp"] != 0, np.nan)
    df["retorno_pct"]  = (df["ganancia_clp"] / costo_safe * 100).round(2)

    # Enriquecer con tipo/pais/sector (importar tarde para evitar dependencias circulares)
    try:
        from dashboard.mappings import get_tipo, get_pais, get_sector
        df["tipo"]   = df.apply(lambda r: get_tipo(r["ticker"], r.get("mercado", "")), axis=1)
        df["pais"]   = df.apply(lambda r: get_pais(r["ticker"], r.get("mercado", "")), axis=1)
        df["sector"] = df.apply(lambda r: get_sector(r["ticker"], r.get("tipo", "")), axis=1)
    except Exception:
        df["tipo"] = df.get("mercado", "—")
        df["pais"] = "—"
        df["sector"] = "—"

    return df


def fetch_price_history(yf_tickers: tuple, period: str = "6mo") -> pd.DataFrame:
    """Histórico de precios para detectar drawdowns y volatilidad."""
    try:
        import yfinance as yf
        raw = yf.download(list(yf_tickers), period=period, interval="1d",
                          auto_adjust=True, progress=False, group_by="ticker")
        if raw.empty:
            return pd.DataFrame()
        if len(yf_tickers) == 1:
            close = raw[["Close"]].copy()
            close.columns = [yf_tickers[0]]
        else:
            try:
                close = raw.xs("Close", axis=1, level=1)
            except KeyError:
                close = raw.xs("Close", axis=1, level=0)
        close.index = pd.to_datetime(close.index)
        return close
    except Exception as e:
        print(f"  ⚠️ No se pudo bajar precios: {e}")
        return pd.DataFrame()


# ── CHECKS ───────────────────────────────────────────────────
def check_concentracion(df: pd.DataFrame) -> list[dict]:
    """Detecta posiciones, sectores o países excesivamente concentrados."""
    alerts = []
    total = df["valor_clp"].sum()
    if total <= 0:
        return alerts

    # 1. Concentración por TICKER
    for _, row in df.iterrows():
        pct = row["valor_clp"] / total * 100
        if pct >= THRESHOLDS["concentracion_ticker_pct"]:
            sev = "critica" if pct >= 30 else "alta"
            alerts.append({
                "categoria":  "concentracion",
                "severidad":  sev,
                "activo":     row["ticker"],
                "titulo":     f"Concentración alta en {row['ticker']}",
                "mensaje":    f"{row['ticker']} representa {pct:.1f}% de tu cartera "
                              f"(${row['valor_clp']:,.0f} CLP). Sobre {THRESHOLDS['concentracion_ticker_pct']:.0f}% "
                              f"hay riesgo idiosincrático significativo.",
                "metricas":   {"pct_cartera": round(pct, 2),
                               "valor_clp": float(row["valor_clp"]),
                               "umbral": THRESHOLDS["concentracion_ticker_pct"]},
                "sugerencia": f"Considera reducir parcialmente la posición o agregar diversificación.",
            })

    # 2. Concentración por SECTOR
    grp = df.groupby("sector")["valor_clp"].sum().sort_values(ascending=False)
    for sector, val in grp.items():
        pct = val / total * 100
        if pct >= THRESHOLDS["concentracion_sector_pct"] and sector not in (None, "—", "Otros"):
            alerts.append({
                "categoria":  "concentracion",
                "severidad":  "media" if pct < 55 else "alta",
                "activo":     "PORTFOLIO",
                "titulo":     f"Cartera concentrada en sector {sector}",
                "mensaje":    f"{pct:.1f}% de tu cartera está en sector '{sector}'. "
                              f"Un shock al sector te golpearía duro.",
                "metricas":   {"sector": sector, "pct": round(pct, 2)},
                "sugerencia": f"Diversifica con activos de otros sectores.",
            })

    # 3. Concentración por PAÍS
    grp_pais = df.groupby("pais")["valor_clp"].sum().sort_values(ascending=False)
    for pais, val in grp_pais.items():
        pct = val / total * 100
        if pct >= THRESHOLDS["concentracion_pais_pct"] and pais not in (None, "—"):
            alerts.append({
                "categoria":  "concentracion",
                "severidad":  "media",
                "activo":     "PORTFOLIO",
                "titulo":     f"Cartera concentrada en {pais}",
                "mensaje":    f"{pct:.1f}% en {pais}. Riesgo país elevado.",
                "metricas":   {"pais": pais, "pct": round(pct, 2)},
                "sugerencia": f"Diversifica geográficamente.",
            })

    return alerts


def check_drawdown(df: pd.DataFrame, prices: pd.DataFrame, yf_map: dict) -> list[dict]:
    """Detecta posiciones con drawdown significativo desde el pico de 90d."""
    alerts = []
    if prices.empty:
        return alerts

    for _, row in df.iterrows():
        tk_yf = yf_map.get(row["ticker"])
        if not tk_yf or tk_yf not in prices.columns:
            continue
        serie = prices[tk_yf].dropna()
        if len(serie) < 30:
            continue

        # Pico 90d → precio actual
        recent = serie.tail(90)
        pico = recent.max()
        actual = recent.iloc[-1]
        dd_pct = (actual - pico) / pico * 100

        if dd_pct <= THRESHOLDS["drawdown_alerta_pct"]:
            sev = "critica" if dd_pct <= THRESHOLDS["drawdown_critico_pct"] else "alta"
            alerts.append({
                "categoria":  "drawdown",
                "severidad":  sev,
                "activo":     row["ticker"],
                "titulo":     f"{row['ticker']} en drawdown de {dd_pct:.1f}%",
                "mensaje":    f"Cayó {abs(dd_pct):.1f}% desde su pico de 90 días "
                              f"({pico:.2f} → {actual:.2f}). Vale {row['valor_clp']:,.0f} CLP "
                              f"({row['valor_clp']/df['valor_clp'].sum()*100:.1f}% cartera).",
                "metricas":   {"drawdown_pct": round(dd_pct, 2),
                               "pico_90d": float(pico),
                               "precio_actual": float(actual),
                               "valor_clp": float(row["valor_clp"])},
                "sugerencia": "Revisa fundamentales. Si la tesis sigue intacta, puede ser oportunidad de promediar. Si no, considera salir.",
            })
    return alerts


def check_volatilidad(df: pd.DataFrame, prices: pd.DataFrame, yf_map: dict) -> list[dict]:
    """Detecta activos cuya volatilidad reciente está muy por sobre su norma."""
    alerts = []
    if prices.empty:
        return alerts

    for _, row in df.iterrows():
        tk_yf = yf_map.get(row["ticker"])
        if not tk_yf or tk_yf not in prices.columns:
            continue
        serie = prices[tk_yf].dropna()
        if len(serie) < 60:
            continue

        ret = serie.pct_change().dropna()
        vol_total = ret.std()
        vol_reciente = ret.tail(20).std()
        if vol_total > 0 and vol_reciente > 2 * vol_total:
            alerts.append({
                "categoria":  "volatilidad",
                "severidad":  "media",
                "activo":     row["ticker"],
                "titulo":     f"{row['ticker']} con volatilidad anormal",
                "mensaje":    f"Vol últimos 20d ({vol_reciente*100:.1f}%) es {vol_reciente/vol_total:.1f}x "
                              f"su norma histórica ({vol_total*100:.1f}%). Algo está pasando.",
                "metricas":   {"vol_reciente": round(float(vol_reciente)*100, 2),
                               "vol_norma": round(float(vol_total)*100, 2),
                               "ratio": round(float(vol_reciente/vol_total), 2)},
                "sugerencia": "Busca noticias o catalizadores recientes. Vol alta puede preceder movimiento grande.",
            })
    return alerts


def check_crypto_exposure(df: pd.DataFrame) -> list[dict]:
    """Crypto > 15% de cartera."""
    alerts = []
    total = df["valor_clp"].sum()
    if total <= 0:
        return alerts

    crypto = df[df["mercado"].str.lower() == "crypto"] if "mercado" in df.columns else pd.DataFrame()
    if not crypto.empty:
        pct = crypto["valor_clp"].sum() / total * 100
        if pct >= THRESHOLDS["crypto_max_pct"]:
            sev = "alta" if pct >= 20 else "media"
            alerts.append({
                "categoria":  "crypto",
                "severidad":  sev,
                "activo":     "PORTFOLIO",
                "titulo":     f"Exposición cripto alta: {pct:.1f}%",
                "mensaje":    f"{pct:.1f}% de tu cartera está en cripto. Por encima de {THRESHOLDS['crypto_max_pct']}% "
                              f"se considera exposición agresiva.",
                "metricas":   {"pct_cripto": round(pct, 2)},
                "sugerencia": "Revisa si esta proporción calza con tu perfil de riesgo.",
            })
    return alerts


def check_cambiaria(df: pd.DataFrame) -> list[dict]:
    """Detecta desbalance USD/CLP."""
    alerts = []
    total = df["valor_clp"].sum()
    if total <= 0:
        return alerts

    pct_clp = df[df["moneda"] == "CLP"]["valor_clp"].sum() / total * 100
    pct_usd = 100 - pct_clp

    # Solo alerta si una moneda > 85%
    if pct_clp >= 85:
        alerts.append({
            "categoria":  "cambiaria",
            "severidad":  "media",
            "activo":     "PORTFOLIO",
            "titulo":     f"Cartera ${pct_clp:.0f}% en CLP",
            "mensaje":    f"Tu cartera está {pct_clp:.0f}% en pesos chilenos. Una devaluación del CLP te perjudica.",
            "metricas":   {"pct_clp": round(pct_clp, 2), "pct_usd": round(pct_usd, 2)},
            "sugerencia": "Considera diversificar con activos en USD.",
        })
    elif pct_usd >= 85:
        alerts.append({
            "categoria":  "cambiaria",
            "severidad":  "baja",
            "activo":     "PORTFOLIO",
            "titulo":     f"Cartera {pct_usd:.0f}% en USD",
            "mensaje":    f"{pct_usd:.0f}% en USD. Si tus gastos son en CLP, una apreciación del peso "
                          f"reduce tu poder adquisitivo medido en CLP.",
            "metricas":   {"pct_clp": round(pct_clp, 2), "pct_usd": round(pct_usd, 2)},
            "sugerencia": "Considera mantener algo de exposición CLP.",
        })

    return alerts


def check_pe_caro(df: pd.DataFrame) -> list[dict]:
    """Detecta posiciones con P/E excesivamente alto (sobrevaloradas)."""
    alerts = []
    try:
        import yfinance as yf
    except ImportError:
        return alerts

    # Solo evaluar top 10 posiciones por valor (no spammear yfinance)
    top = df.nlargest(10, "valor_clp")
    for _, row in top.iterrows():
        try:
            tk = row["ticker"]
            tk_yf = f"{tk}.SN" if row.get("mercado") == "nacional" else tk
            info = yf.Ticker(tk_yf).info
            pe = info.get("trailingPE")
            if pe and pe > THRESHOLDS["pe_caro"]:
                sev = "alta" if pe > THRESHOLDS["pe_alarma"] else "media"
                alerts.append({
                    "categoria":  "valuacion",
                    "severidad":  sev,
                    "activo":     tk,
                    "titulo":     f"{tk} con P/E elevado ({pe:.1f}x)",
                    "mensaje":    f"P/E de {pe:.1f}x es alto. Sobre {THRESHOLDS['pe_caro']}x suele "
                                  f"reflejar expectativas optimistas que dejan poco margen de error.",
                    "metricas":   {"pe": round(float(pe), 2)},
                    "sugerencia": "Revisa earnings growth. Si no justifica el múltiplo, riesgo de corrección.",
                })
        except Exception:
            continue
    return alerts


# ── INSERTAR EN SUPABASE ─────────────────────────────────────
def save_alerts(alerts: list) -> dict:
    """
    Inserta alertas en portfolio_alerts.
    ANTES de insertar: desactiva alertas activas previas con misma (categoria, activo)
    para que no haya duplicados visibles en el email/dashboard.
    """
    if not alerts:
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}

    sb = get_client()
    ins = dup = err = 0

    # 1. Desactivar TODAS las alertas activas previas que vamos a regenerar
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

    # 2. Insertar las nuevas
    for a in alerts:
        try:
            sb.table("portfolio_alerts").insert(a).execute()
            ins += 1
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg or "uniq_alert_per_day" in msg:
                # Si ya hay una de hoy con misma key, la actualizamos como activa
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
                    print(f"  ❌ {a['categoria']}/{a['activo']}: {str(e)[:120]}")
    return {"insertadas": ins, "duplicadas": dup, "errores": err}


# ── MAIN ─────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🏥 PORTFOLIO HEALTH MONITOR")
    print("=" * 60)

    df = load_portfolio()
    if df.empty:
        print("⚠️ Cartera vacía. Salida.")
        return

    print(f"\n📊 {len(df)} posiciones · Total: ${df['valor_clp'].sum():,.0f} CLP\n")

    all_alerts = []
    print("▶ Concentración...")
    a = check_concentracion(df); print(f"  {len(a)} alertas"); all_alerts += a

    print("▶ Exposición cripto...")
    a = check_crypto_exposure(df); print(f"  {len(a)} alertas"); all_alerts += a

    print("▶ Exposición cambiaria...")
    a = check_cambiaria(df); print(f"  {len(a)} alertas"); all_alerts += a

    # Drawdown y volatilidad necesitan histórico de precios
    print("▶ Descargando histórico de precios (yfinance)...")
    yf_map = {
        row["ticker"]: (f"{row['ticker']}.SN" if row.get("mercado") == "nacional" else row["ticker"])
        for _, row in df.iterrows()
        if pd.notna(row.get("ticker")) and row["ticker"] != "PORTFOLIO_CL"
    }
    yf_tickers = tuple(sorted(set(yf_map.values())))
    prices = fetch_price_history(yf_tickers, "6mo")

    print("▶ Drawdown...")
    a = check_drawdown(df, prices, yf_map); print(f"  {len(a)} alertas"); all_alerts += a

    print("▶ Volatilidad anormal...")
    a = check_volatilidad(df, prices, yf_map); print(f"  {len(a)} alertas"); all_alerts += a

    print("▶ P/E elevado...")
    a = check_pe_caro(df); print(f"  {len(a)} alertas"); all_alerts += a

    print(f"\n📋 Total alertas detectadas: {len(all_alerts)}")

    if all_alerts:
        result = save_alerts(all_alerts)
        print(f"\n✅ Insertadas: {result['insertadas']}")
        print(f"⏭  Ya existían (hoy): {result['duplicadas']}")
        print(f"❌ Errores: {result['errores']}")

    print("=" * 60)


if __name__ == "__main__":
    main()
