# ============================================================
# SELL ENGINE v1 — Señales de venta / protección de utilidades
#
# Lee investor_profile.yaml (perfil, límites, horizontes) y genera
# alertas de venta que el sistema de compras NUNCA genera:
#
#   1. Concentración individual: posición > max_pct_posicion_individual
#   2. Concentración por bucket: bucket > max_pct_bucket
#   3. EVALUAR al duplicar: especulativa con +100% → contexto para decidir
#   4. Trailing guardrail: ganadora especulativa que cae >2σ desde máximo
#   5. Eventos programados: lockups, fechas conocidas (ej. VCX sept 2026)
#   6. Liquidez emprendimiento: % líquido/estable < mínimo tocable
#
# NO vende — solo alerta. Escribe en portfolio_alerts.
#
# Uso:
#   python -m intelligence.sell_engine
#   python -m intelligence.sell_engine --dry-run
# ============================================================

import sys, argparse, warnings
from datetime import date, datetime
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

PROFILE_PATH = Path(__file__).parent / "config" / "investor_profile.yaml"


# ── LOADERS ─────────────────────────────────────────────────
def load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_usdclp() -> float:
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


def load_cartera(usd_clp: float) -> pd.DataFrame:
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return df
    for c in ["cantidad", "precio_compra", "precio_actual"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["valor_local"] = df["cantidad"] * df["precio_actual"]
    df["valor_usd"] = df.apply(
        lambda r: r["valor_local"] / usd_clp if r.get("moneda") == "CLP" else r["valor_local"],
        axis=1,
    )
    df["costo_local"] = df["cantidad"] * df["precio_compra"]
    # Ganancia % solo válida si hay precio_compra > 0
    df["ganancia_pct"] = np.where(
        df["precio_compra"] > 0,
        (df["precio_actual"] / df["precio_compra"] - 1) * 100,
        np.nan,
    )
    return df


def yf_ticker_for(ticker: str, mercado: str) -> str:
    if mercado == "nacional":
        base = ticker.replace("_STG", "") if ticker.endswith("_STG") else ticker
        return f"{base}.SN"
    if mercado == "crypto":
        return f"{ticker}-USD"
    return ticker


def clasificar(ticker: str, profile: dict) -> str:
    """Bucket de horizonte del ticker según el perfil. Default: satelite."""
    clasif = profile.get("clasificacion", {})
    for bucket in ("core", "conviccion", "satelite", "especulativo"):
        if ticker in clasif.get(bucket, []):
            return bucket
    return "satelite"


# ── 1+2. CONCENTRACIÓN ──────────────────────────────────────
def check_concentracion(df: pd.DataFrame, profile: dict) -> list:
    alerts = []
    limites = profile.get("limites", {})
    max_pos = limites.get("max_pct_posicion_individual", 12.0)
    core_tickers = set(profile.get("clasificacion", {}).get("core", []))

    intl = df[df["mercado"].isin(["internacional", "crypto"])].copy()
    if intl.empty:
        return alerts
    total_intl = intl["valor_usd"].sum()
    if total_intl <= 0:
        return alerts

    # Posición individual (excluye ETFs core, diversificados por construcción)
    for _, row in intl.iterrows():
        tk = row["ticker"]
        if tk in core_tickers or tk == "PORTFOLIO_CL":
            continue
        pct = row["valor_usd"] / total_intl * 100
        if pct > max_pos:
            exceso_usd = (pct - max_pos) / 100 * total_intl
            alerts.append({
                "categoria":  "venta_concentracion",
                "severidad":  "alta",
                "activo":     tk,
                "titulo":     f"CONCENTRACIÓN: {tk} es {pct:.1f}% del portafolio",
                "mensaje":    f"{tk} vale USD {row['valor_usd']:,.0f} = {pct:.1f}% del portafolio "
                              f"internacional (límite: {max_pos:.0f}%). "
                              f"Exceso sobre límite: USD {exceso_usd:,.0f}.",
                "metricas":   {"pct_portafolio": round(pct, 2), "limite": max_pos,
                               "valor_usd": round(row["valor_usd"], 0),
                               "exceso_usd": round(exceso_usd, 0)},
                "sugerencia": f"Evaluar trim de ~USD {exceso_usd:,.0f} para volver al límite de {max_pos:.0f}%.",
            })
    return alerts


# ── 3. EVALUAR AL DUPLICAR ──────────────────────────────────
def check_duplicadas(df: pd.DataFrame, profile: dict, metrics_map: dict) -> list:
    """Especulativas con ganancia > umbral → alerta EVALUAR con contexto."""
    alerts = []
    pt = profile.get("profit_taking", {})
    umbral = pt.get("umbral_ganancia_pct", 100)

    for _, row in df.iterrows():
        tk = row["ticker"]
        if pd.isna(row.get("ganancia_pct")) or row["ganancia_pct"] < umbral:
            continue
        if clasificar(tk, profile) not in ("especulativo", "satelite"):
            continue  # convicción y core se dejan correr

        m = metrics_map.get(tk, {})
        contexto = []
        if m.get("pct_20d") is not None:
            contexto.append(f"momentum 20d: {m['pct_20d']:+.1f}%")
        if m.get("pct_from_ath") is not None:
            contexto.append(f"distancia de ATH: {m['pct_from_ath']:.1f}%")
        if m.get("volume_ratio") is not None:
            contexto.append(f"volumen: {m['volume_ratio']:.1f}x normal")
        ctx_str = " | ".join(contexto) if contexto else "sin datos de mercado"

        alerts.append({
            "categoria":  "venta_evaluar",
            "severidad":  "media",
            "activo":     tk,
            "titulo":     f"EVALUAR: {tk} +{row['ganancia_pct']:.0f}% sobre costo",
            "mensaje":    f"{tk} vale USD {row['valor_usd']:,.0f} con ganancia de "
                          f"{row['ganancia_pct']:+.0f}% sobre tu costo. Contexto: {ctx_str}. "
                          f"Decisión según tu política: agregar más, mantener o recortar "
                          f"según proyecciones y potencial.",
            "metricas":   {"ganancia_pct": round(row["ganancia_pct"], 1),
                           "valor_usd": round(row["valor_usd"], 0),
                           "pct_20d": m.get("pct_20d"), "pct_from_ath": m.get("pct_from_ath")},
            "sugerencia": "EVALUAR con contexto: si momentum fuerte y tesis mejorando, mantener/agregar. "
                          "Si momentum quebrado o tesis dudosa, recortar 25-30%.",
        })
    return alerts


# ── 4. TRAILING GUARDRAIL ───────────────────────────────────
def check_trailing(df: pd.DataFrame, profile: dict, metrics_map: dict) -> list:
    """Ganadora especulativa que cae >Nσ desde su máximo de 20d → proteger."""
    alerts = []
    pt = profile.get("profit_taking", {}).get("trailing_guardrail", {})
    aplica_a = set(pt.get("aplica_a", ["especulativo"]))
    min_gan = pt.get("min_ganancia_pct", 50)
    sigma_lim = pt.get("sigma_caida", 2.0)

    for _, row in df.iterrows():
        tk = row["ticker"]
        if pd.isna(row.get("ganancia_pct")) or row["ganancia_pct"] < min_gan:
            continue
        if clasificar(tk, profile) not in aplica_a:
            continue
        m = metrics_map.get(tk)
        if not m or m.get("drawdown_sigma") is None:
            continue

        if m["drawdown_sigma"] >= sigma_lim:
            alerts.append({
                "categoria":  "venta_trailing",
                "severidad":  "alta",
                "activo":     tk,
                "titulo":     f"PROTEGER UTILIDADES: {tk} cayó {m['drawdown_20d_pct']:.1f}% desde máximo",
                "mensaje":    f"{tk} (ganancia {row['ganancia_pct']:+.0f}% sobre costo) cayó "
                              f"{m['drawdown_20d_pct']:.1f}% desde su máximo de 20 días "
                              f"= {m['drawdown_sigma']:.1f}σ de su volatilidad normal. "
                              f"El quiebre es estadísticamente significativo, no ruido.",
                "metricas":   {"drawdown_pct": round(m["drawdown_20d_pct"], 1),
                               "sigma": round(m["drawdown_sigma"], 1),
                               "ganancia_pct": round(row["ganancia_pct"], 1),
                               "valor_usd": round(row["valor_usd"], 0)},
                "sugerencia": pt.get("sugerencia", "Evaluar trim parcial o stop mental."),
            })
    return alerts


# ── 5. EVENTOS PROGRAMADOS ──────────────────────────────────
def check_eventos(profile: dict) -> list:
    alerts = []
    hoy = date.today()
    for ev in profile.get("eventos", []):
        try:
            fecha_ev = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        dias = (fecha_ev - hoy).days
        aviso = ev.get("dias_aviso", 14)
        if 0 <= dias <= aviso:
            alerts.append({
                "categoria":  "evento_programado",
                "severidad":  "alta" if dias <= 7 else "media",
                "activo":     ev.get("ticker", "?"),
                "titulo":     f"EVENTO en {dias}d: {ev.get('tipo', 'evento')} de {ev.get('ticker')}",
                "mensaje":    f"{ev.get('nota', '')} Fecha: {ev['fecha']} ({dias} días).",
                "metricas":   {"fecha": ev["fecha"], "dias_restantes": dias,
                               "tipo": ev.get("tipo")},
                "sugerencia": ev.get("nota", "Revisar y decidir antes de la fecha."),
            })
    return alerts


# ── 6. LIQUIDEZ EMPRENDIMIENTO ──────────────────────────────
def check_liquidez(df: pd.DataFrame, profile: dict) -> list:
    """El 20-30% tocable en 1-2 años debe existir en activos líquidos/estables."""
    alerts = []
    obj = profile.get("objetivo_emprendimiento", {})
    pct_min = obj.get("pct_portafolio_tocable", [20, 30])[0]
    elegibles = set(obj.get("activos_elegibles_liquidez", []))
    if not elegibles or df.empty:
        return alerts

    total_usd = df["valor_usd"].sum()
    liquido_usd = df[df["ticker"].isin(elegibles)]["valor_usd"].sum()
    pct_liquido = liquido_usd / total_usd * 100 if total_usd > 0 else 0

    if pct_liquido < pct_min:
        deficit_usd = (pct_min - pct_liquido) / 100 * total_usd
        alerts.append({
            "categoria":  "liquidez_emprendimiento",
            "severidad":  "media",
            "activo":     "PORTFOLIO",
            "titulo":     f"LIQUIDEZ: solo {pct_liquido:.0f}% en activos tocables (objetivo {pct_min:.0f}%+)",
            "mensaje":    f"Tu plan de emprender en 1-2 años requiere {pct_min:.0f}-30% del "
                          f"portafolio en activos líquidos y estables. Hoy tienes "
                          f"USD {liquido_usd:,.0f} ({pct_liquido:.0f}%) en elegibles. "
                          f"Déficit: USD {deficit_usd:,.0f}.",
            "metricas":   {"pct_liquido": round(pct_liquido, 1), "objetivo_min": pct_min,
                           "liquido_usd": round(liquido_usd, 0),
                           "deficit_usd": round(deficit_usd, 0)},
            "sugerencia": f"Dirigir próximas compras (DCA u oportunísticas) hacia ETFs core "
                          f"hasta cerrar el déficit de USD {deficit_usd:,.0f}, o reclasificar "
                          f"posiciones estables como elegibles en investor_profile.yaml.",
        })
    return alerts


# ── 7. EXPOSICIÓN POR FACTOR (clustering de correlaciones) ──
def check_factor_exposure(df: pd.DataFrame, profile: dict, force: bool = False) -> list:
    """Posiciones que se mueven juntas son UNA apuesta aunque sean tickers
    distintos (ej: NVDA+TSM+ASML+MU+AVGO+CRWV = cadena IA). Clustering greedy
    por correlación de retornos 6m; alerta si el cluster mayor supera
    max_pct_factor. Corre solo los lunes (la concentración no cambia a diario)."""
    alerts = []
    if not force and date.today().weekday() != 0:
        return alerts
    max_factor = profile.get("limites", {}).get("max_pct_factor", 40.0)

    # Posiciones internacionales relevantes (> USD 500), EXCLUYENDO ETFs core:
    # el core ES el factor mercado (diversificado por construcción) — incluirlo
    # hace que todo clusterice con VOO y esconde las apuestas temáticas reales
    core = set(profile.get("clasificacion", {}).get("core", []))
    pos = df[(df["mercado"] == "internacional") & (df["valor_usd"] > 500)
             & (~df["ticker"].isin(core))].copy()
    if len(pos) < 5:
        return alerts
    total_usd = df[df["mercado"].isin(["internacional", "crypto"])]["valor_usd"].sum()
    valores = dict(zip(pos["ticker"], pos["valor_usd"]))
    tickers = sorted(valores.keys())

    try:
        import yfinance as yf
        raw = yf.download(tickers, period="6mo", interval="1d",
                          auto_adjust=True, progress=False, group_by="ticker")
        closes = {}
        for tk in tickers:
            try:
                s = raw[tk]["Close"].dropna() if hasattr(raw.columns, "levels") else raw["Close"].dropna()
                if len(s) >= 60:
                    closes[tk] = s.pct_change().dropna()
            except Exception:
                continue
        if len(closes) < 5:
            return alerts
        rets = pd.DataFrame(closes).dropna()
        corr = rets.corr()
    except Exception as e:
        print(f"  factor: error bajando precios: {str(e)[:80]}")
        return alerts

    # Clustering greedy: semilla = posición más grande sin asignar;
    # se agregan los tickers con corr > 0.6 con la semilla
    UMBRAL = 0.6
    sin_asignar = sorted(corr.columns, key=lambda t: -valores.get(t, 0))
    clusters = []
    while sin_asignar:
        semilla = sin_asignar.pop(0)
        grupo = [semilla]
        for tk in list(sin_asignar):
            if corr.loc[semilla, tk] > UMBRAL:
                grupo.append(tk)
                sin_asignar.remove(tk)
        clusters.append(grupo)

    for grupo in clusters:
        if len(grupo) < 3:
            continue  # 2 tickers correlacionados no es "factor"
        peso_usd = sum(valores.get(tk, 0) for tk in grupo)
        pct = peso_usd / total_usd * 100 if total_usd > 0 else 0
        if pct > max_factor:
            corr_prom = float(pd.DataFrame(
                [[corr.loc[a, b] for b in grupo] for a in grupo]).values.mean())
            alerts.append({
                "categoria":  "factor_concentracion",
                "severidad":  "alta",
                "activo":     grupo[0],
                "titulo":     f"FACTOR: {len(grupo)} posiciones correlacionadas = {pct:.0f}% del portafolio",
                "mensaje":    f"Estas {len(grupo)} posiciones se mueven juntas "
                              f"(correlación promedio {corr_prom:.2f}): {', '.join(grupo)}. "
                              f"Juntas son USD {peso_usd:,.0f} = {pct:.0f}% del portafolio "
                              f"(límite factor: {max_factor:.0f}%). Son UNA apuesta, "
                              f"no {len(grupo)} — si la tesis común se rompe, caen juntas.",
                "metricas":   {"tickers": grupo, "pct_portafolio": round(pct, 1),
                               "corr_promedio": round(corr_prom, 2),
                               "valor_usd": round(peso_usd, 0)},
                "sugerencia": f"Diversificación real: próximas compras fuera de este factor, "
                              f"o trim de las posiciones con peor tesis del grupo.",
            })
    return alerts


# ── MARKET METRICS (para contexto de duplicadas y trailing) ─
def fetch_metrics(df: pd.DataFrame, profile: dict) -> dict:
    """Descarga 6m de historia solo para tickers que necesitan contexto:
    especulativas/satélites con ganancia > 50%."""
    candidatos = []
    for _, row in df.iterrows():
        tk = row["ticker"]
        if tk == "PORTFOLIO_CL" or pd.isna(row.get("ganancia_pct")):
            continue
        if row["ganancia_pct"] >= 50 and clasificar(tk, profile) in ("especulativo", "satelite"):
            candidatos.append((tk, row.get("mercado", "internacional")))

    if not candidatos:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        return {}

    yf_map = {tk: yf_ticker_for(tk, mercado) for tk, mercado in candidatos}
    raw = yf.download(list(set(yf_map.values())), period="6mo", interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    if raw.empty:
        return {}

    metrics = {}
    for tk, yf_tk in yf_map.items():
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if yf_tk not in raw.columns.get_level_values(0):
                    continue
                close = raw[yf_tk]["Close"].dropna()
                volume = raw[yf_tk].get("Volume")
            else:
                close = raw["Close"].dropna()
                volume = raw.get("Volume")
            if len(close) < 30:
                continue

            p = float(close.iloc[-1])
            max_20d = float(close.tail(20).max())
            dd_pct = (p / max_20d - 1) * 100  # negativo si cayó

            # Volatilidad diaria 60d → σ del drawdown esperado en ~20d
            rets = close.pct_change().dropna().tail(60)
            vol_d = float(rets.std())
            sigma_20d = vol_d * np.sqrt(20) * 100  # en %
            dd_sigma = abs(dd_pct) / sigma_20d if sigma_20d > 0 else None

            ath = float(close.max())
            m = {
                "precio_actual": p,
                "drawdown_20d_pct": dd_pct,
                "drawdown_sigma": dd_sigma if dd_pct < 0 else 0.0,
                "pct_from_ath": (p / ath - 1) * 100,
                "pct_20d": (p / float(close.iloc[-min(21, len(close))]) - 1) * 100,
                "volume_ratio": None,
            }
            if volume is not None and len(volume.dropna()) >= 60:
                v = volume.dropna()
                va = float(v.tail(60).mean())
                m["volume_ratio"] = float(v.tail(5).mean()) / va if va > 0 else None
            metrics[tk] = m
        except Exception:
            continue
    return metrics


# ── SAVE ────────────────────────────────────────────────────
OWNED_CATEGORIES = ["venta_concentracion", "venta_trailing", "venta_evaluar",
                    "evento_programado", "liquidez_emprendimiento",
                    "factor_concentracion"]


def save_alerts(alerts: list) -> dict:
    sb = get_client()
    ins = dup = err = 0
    # Desactivar TODAS las previas de categorías propias (evita señales zombie)
    for cat in OWNED_CATEGORIES:
        try:
            sb.table("portfolio_alerts").update({"activo_alerta": False}) \
              .eq("activo_alerta", True).eq("categoria", cat).execute()
        except Exception:
            pass
    if not alerts:
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}
    for a in alerts:
        try:
            sb.table("portfolio_alerts").insert(a).execute()
            ins += 1
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                dup += 1
            else:
                err += 1
                if err <= 3:
                    print(f"  {a['activo']}: {str(e)[:120]}")
    return {"insertadas": ins, "duplicadas": dup, "errores": err}


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("SELL ENGINE v1 — Señales de venta y protección")
    print("=" * 60)

    profile = load_profile()
    usd_clp = get_usdclp()
    print(f"\nUSD/CLP: {usd_clp:.2f}")

    df = load_cartera(usd_clp)
    if df.empty:
        print("Cartera vacía.")
        return
    total = df["valor_usd"].sum()
    print(f"Cartera: {len(df)} posiciones, USD {total:,.0f} total")

    print("\nDescargando contexto de mercado para ganadoras...")
    metrics_map = fetch_metrics(df, profile)
    print(f"  {len(metrics_map)} tickers con contexto")

    all_alerts = []
    checks = [
        ("Concentración", lambda: check_concentracion(df, profile)),
        ("Duplicadas (EVALUAR)", lambda: check_duplicadas(df, profile, metrics_map)),
        ("Trailing guardrail", lambda: check_trailing(df, profile, metrics_map)),
        ("Eventos programados", lambda: check_eventos(profile)),
        ("Liquidez emprendimiento", lambda: check_liquidez(df, profile)),
        ("Exposición por factor (lunes)", lambda: check_factor_exposure(df, profile)),
    ]
    for nombre, fn in checks:
        try:
            found = fn()
            all_alerts.extend(found)
            print(f"{nombre}: {len(found)} alertas")
        except Exception as e:
            print(f"{nombre}: ERROR {str(e)[:100]}")

    sev_order = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "info": 4}
    all_alerts.sort(key=lambda a: sev_order.get(a.get("severidad", "info"), 99))

    print(f"\nTotal señales de venta/protección: {len(all_alerts)}")
    for a in all_alerts:
        print(f"  [{a['severidad'].upper():6s}] {a['titulo']}")

    if args.dry_run:
        print("\nDRY RUN — no se guardó nada")
        return

    result = save_alerts(all_alerts)
    print(f"\nInsertadas: {result['insertadas']} | Duplicadas: {result['duplicadas']} | Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
