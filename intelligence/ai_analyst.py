# ============================================================
# AI ANALYST v2 — Analisis de noticias con contexto de watchlist
#
# Procesa noticias pendientes (market_news.procesado_ai = false)
# y genera analisis estructurado en market_intelligence.
#
# NUEVO en v2:
#   - Inyecta watchlist completa (tiers + buckets + entry targets)
#   - Pide a Claude que identifique oportunidades de watchlist
#   - Cross-reference noticias con buckets tematicos
#
# Requiere: ANTHROPIC_API_KEY
# Uso: python -m intelligence.ai_analyst --limit 30
# ============================================================

import sys, os, json, argparse
from datetime import datetime
import warnings
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

MODEL = "claude-haiku-4-5"
USD_CLP = 901.76
WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"


def get_api_key() -> str:
    k = os.getenv("ANTHROPIC_API_KEY")
    if k:
        return k
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def load_portfolio_context() -> str:
    """Resumen breve de la cartera para inyectar al prompt."""
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return "Cartera vacia."

    for c in ["precio_actual", "cantidad", "precio_compra"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["valor_usd"] = df["cantidad"] * df["precio_actual"]
    df["valor_clp"] = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP,
        axis=1
    )

    total = df["valor_clp"].sum()
    top = df.nlargest(20, "valor_clp")
    lines = [f"Valor total cartera: ${total:,.0f} CLP (~USD {total/USD_CLP:,.0f})"]
    lines.append("Top 20 posiciones (% cartera):")
    for _, row in top.iterrows():
        pct = row["valor_clp"] / total * 100
        lines.append(f"  - {row['ticker']:14s} {pct:5.1f}%  ({row.get('mercado','?')})")
    return "\n".join(lines)


def load_watchlist_context() -> str:
    """Construye contexto de watchlist para inyectar al prompt."""
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            wl = yaml.safe_load(f)
    except FileNotFoundError:
        return ""

    lines = []

    # Recurrente plan (tickers que ya compra)
    lines.append("PLAN RECURRENTE (DCA semanal):")
    for item in wl.get("recurrente", []):
        lines.append(f"  - {item['ticker']:8s} USD {item['usd_sem']}/sem  [{item.get('bucket','')}] {item.get('tesis','')}")

    # Watchlist tiers
    lines.append("\nWATCHLIST TIER 1 (alta conviccion, entry targets):")
    for item in wl.get("watchlist", {}).get("tier1", []):
        entry = item.get("entry_usd", "?")
        lines.append(f"  - {item['ticker']:8s} entry USD {entry}  [{item.get('bucket','')}] {item.get('tesis','')}")

    lines.append("\nWATCHLIST TIER 2 (monitoreo activo):")
    for item in wl.get("watchlist", {}).get("tier2", []):
        lines.append(f"  - {item['ticker']:8s} [{item.get('bucket','')}] {item.get('tesis','')}")

    # Buckets
    lines.append("\nBUCKETS TEMATICOS (areas de interes):")
    for b in wl.get("buckets", []):
        lines.append(f"  - {b['nombre']}: {', '.join(b.get('keywords', []))}")

    # Pending actions
    lines.append("\nACCIONES PENDIENTES:")
    for item in wl.get("acciones_pendientes", []):
        lines.append(f"  - {item.get('accion','')} {item['ticker']} USD {item.get('monto_usd','?')} [{item.get('urgencia','')}] {item.get('nota','')}")

    return "\n".join(lines)


# ── PROMPT v2 ───────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un analista de inversiones senior. Analizas noticias financieras y determinas su impacto sobre el portafolio Y watchlist de tu cliente.

REGLAS:
1. Distingue SIEMPRE entre ruido y senal real. Senal = fuente confiable + especifica + mecanismo claro + magnitud relevante.
2. Ruido = especulacion, fuente debil, reciclado, sin mecanismo claro.
3. NO inventes datos. Si no aporta evidencia, di "confianza baja" o "ruido".
4. Si NO afecta al portafolio NI watchlist, di relevancia 10-20 y "neutro".
5. IMPORTANTE: Si la noticia afecta un ticker del WATCHLIST (no solo cartera), indica la oportunidad. El cliente quiere saber si una noticia crea un punto de entrada en algo que ya monitorea.
6. Si la noticia se relaciona con un BUCKET tematico, menciona que tickers del plan/watchlist se benefician o perjudican.

Responde SIEMPRE en JSON valido:

{
  "relevancia_pct": 0-100,
  "tipo": "riesgo" | "oportunidad" | "neutro",
  "horizonte": "intraday" | "semanas" | "meses" | "estructural",
  "confianza_senal": "ruido" | "baja" | "media" | "alta",
  "tickers_afectados": ["TICKER1", "TICKER2"],
  "sectores_afectados": ["Sector1"],
  "impacto_estimado_pct": -10.0 a 10.0,
  "pct_cartera_expuesta": 0.0 a 100.0,
  "resumen_esp": "2-3 lineas en espanol, claro y directo",
  "razonamiento": "Por que es relevante. Mecanismo de impacto.",
  "contraargumento": "Lo mas fuerte en contra de actuar.",
  "accion_sugerida": "Accion concreta: 'mantener', 'comprar X si baja a Y', 'monitorear Z', etc.",
  "watchlist_relevance": "Si aplica: que ticker de watchlist se beneficia y por que. Si no aplica: null"
}
"""


def analyze_news_item(client, noticia: dict, portfolio_context: str, watchlist_context: str):
    """Llama a Claude con una noticia y retorna analisis JSON."""
    user_msg = f"""## CARTERA DEL CLIENTE
{portfolio_context}

## WATCHLIST Y PLAN DE INVERSIONES
{watchlist_context}

## NOTICIA A ANALIZAR
Titulo: {noticia['titulo']}
Fuente: {noticia['fuente']}
Fecha: {noticia.get('fecha_noticia', '?')}
URL: {noticia.get('url', '')}

Resumen:
{noticia.get('resumen', '')}

Tickers preliminarmente detectados: {noticia.get('tickers_mencionados') or []}
Sectores preliminares: {noticia.get('sectores_mencionados') or []}

## TAREA
Analiza esta noticia considerando TANTO el portafolio actual como la watchlist/plan de inversiones. Si la noticia crea una oportunidad para comprar algo del watchlist, indicalo claramente. Responde SOLO con el JSON."""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        txt = resp.content[0].text.strip()

        if "```" in txt:
            import re
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                txt = m.group(0)
        return json.loads(txt)
    except json.JSONDecodeError as e:
        print(f"    JSON invalido: {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    Error API: {str(e)[:100]}")
        return None


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30,
                        help="Cuantas noticias procesar en este batch")
    parser.add_argument("--min-relevancia", type=int, default=25,
                        help="Score preliminar minimo para gastar tokens AI")
    args = parser.parse_args()

    print("=" * 60)
    print("AI ANALYST v2 — Noticias + Watchlist cross-reference")
    print("=" * 60)

    api_key = get_api_key()
    if not api_key:
        print("\nFalta ANTHROPIC_API_KEY.")
        sys.exit(1)

    try:
        from anthropic import Anthropic
    except ImportError:
        print("\nFalta paquete anthropic. pip install anthropic")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    sb = get_client()

    # 1. Cargar contextos (1 vez por ejecucion)
    print("\nCargando contexto de cartera...")
    portfolio_ctx = load_portfolio_context()
    print("Cargando contexto de watchlist...")
    watchlist_ctx = load_watchlist_context()

    # 2. Noticias pendientes
    print(f"\nBuscando noticias pendientes (relevancia >= {args.min_relevancia})...")
    r = (sb.table("market_news")
           .select("*")
           .eq("procesado_ai", False)
           .gte("relevancia_preliminar", args.min_relevancia)
           .order("relevancia_preliminar", desc=True)
           .order("fecha_noticia", desc=True)
           .limit(args.limit)
           .execute())
    noticias = r.data
    print(f"   {len(noticias)} noticias a procesar\n")

    if not noticias:
        print("Nada pendiente.")
        return

    # 3. Procesar cada noticia
    ok = err = 0
    for i, n in enumerate(noticias, 1):
        print(f"[{i}/{len(noticias)}] {n['titulo'][:70]}...")
        analisis = analyze_news_item(client, n, portfolio_ctx, watchlist_ctx)

        if not analisis:
            err += 1
            continue

        required = {"relevancia_pct", "tipo", "confianza_senal", "resumen_esp"}
        if not required.issubset(analisis.keys()):
            print(f"    Faltan campos: {required - set(analisis.keys())}")
            err += 1
            continue

        try:
            row = {
                "noticia_id":           n["id"],
                "relevancia_pct":       int(analisis.get("relevancia_pct", 0)),
                "tipo":                 analisis.get("tipo", "neutro"),
                "horizonte":            analisis.get("horizonte"),
                "confianza_senal":      analisis.get("confianza_senal", "baja"),
                "tickers_afectados":    analisis.get("tickers_afectados") or [],
                "sectores_afectados":   analisis.get("sectores_afectados") or [],
                "impacto_estimado_pct": float(analisis.get("impacto_estimado_pct") or 0),
                "pct_cartera_expuesta": float(analisis.get("pct_cartera_expuesta") or 0),
                "resumen_esp":          analisis.get("resumen_esp"),
                "razonamiento":         analisis.get("razonamiento"),
                "contraargumento":      analisis.get("contraargumento"),
                "accion_sugerida":      analisis.get("accion_sugerida"),
                "modelo_usado":         MODEL,
            }

            # Store watchlist_relevance in razonamiento if present
            wl_rel = analisis.get("watchlist_relevance")
            if wl_rel and wl_rel != "null" and str(wl_rel).lower() != "none":
                row["razonamiento"] = (row.get("razonamiento") or "") + f"\n\nWATCHLIST: {wl_rel}"

            sb.table("market_intelligence").insert(row).execute()
            sb.table("market_news").update({"procesado_ai": True}).eq("id", n["id"]).execute()
            ok += 1
            print(f"    {analisis['tipo']:12s} relev:{analisis['relevancia_pct']:>3} senal:{analisis['confianza_senal']}")
        except Exception as e:
            print(f"    DB error: {str(e)[:100]}")
            err += 1

    print(f"\n{'='*60}")
    print(f"Procesadas: {ok}")
    print(f"Errores:    {err}")


if __name__ == "__main__":
    main()
