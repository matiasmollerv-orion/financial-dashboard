# ============================================================
# AI ANALYST — Análisis profundo de noticias con Claude
# Procesa noticias pendientes (market_news.procesado_ai = false)
# y genera análisis estructurado en market_intelligence.
#
# Requiere: ANTHROPIC_API_KEY (env var o Streamlit secret)
# Uso: python -m intelligence.ai_analyst --limit 30
# ============================================================

import sys, os, json, argparse
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")

# Cargar .env automáticamente (override=True por si shell tiene vars vacías)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import pandas as pd
from database.supabase_client import get_client

MODEL = "claude-haiku-4-5"  # rápido y barato
USD_CLP = 901.76


def get_api_key() -> str:
    """Lee ANTHROPIC_API_KEY de env o Streamlit secrets."""
    k = os.getenv("ANTHROPIC_API_KEY")
    if k:
        return k
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def load_portfolio_context() -> str:
    """Construye un resumen breve de la cartera para inyectar al prompt."""
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return "Cartera vacía."

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


# ── PROMPT PRINCIPAL ─────────────────────────────────────────
SYSTEM_PROMPT = """Eres un analista de inversiones senior con 20 años de experiencia en mercados emergentes y desarrollados. Tu trabajo es analizar una noticia financiera y determinar su impacto real sobre el portafolio específico de tu cliente.

Tu análisis debe ser DIRECTO, ACCIONABLE y DESPROVISTO DE HEDGING INNECESARIO. No eres un robot legal. Da una opinión clara y fundamentada.

Reglas importantes:
1. Distingue SIEMPRE entre ruido y señal real. Una noticia es señal cuando: viene de fuente confiable + es específica + tiene mecanismo claro de impacto + magnitud relevante.
2. Una noticia es ruido cuando: es especulación, viene de fuente débil, recicla algo ya conocido, o no tiene mecanismo claro.
3. NO inventes datos. Si la noticia no aporta evidencia concreta, di "confianza baja" o "ruido".
4. Si la noticia NO afecta significativamente al portafolio del cliente, di "relevancia: 10-20" y "neutro". No infles relevancia.

Responde SIEMPRE en JSON válido, con esta estructura exacta:

{
  "relevancia_pct": 0-100,
  "tipo": "riesgo" | "oportunidad" | "neutro",
  "horizonte": "intraday" | "semanas" | "meses" | "estructural",
  "confianza_senal": "ruido" | "baja" | "media" | "alta",
  "tickers_afectados": ["TICKER1", "TICKER2"],
  "sectores_afectados": ["Sector1"],
  "impacto_estimado_pct": -10.0 a 10.0,
  "pct_cartera_expuesta": 0.0 a 100.0,
  "resumen_esp": "2-3 líneas en español, claro",
  "razonamiento": "Por qué es relevante (o no). Mecanismo de impacto específico.",
  "contraargumento": "Lo más fuerte que se puede decir EN CONTRA de actuar sobre esta noticia.",
  "accion_sugerida": "Acción concreta: 'mantener', 'reducir X 5%', 'monitorear', 'aumentar Y si baja N%', etc."
}
"""


def analyze_news_item(client, noticia: dict, portfolio_context: str):
    """Llama a Claude con una noticia y retorna análisis JSON."""
    user_msg = f"""## CARTERA DEL CLIENTE
{portfolio_context}

## NOTICIA A ANALIZAR
Título: {noticia['titulo']}
Fuente: {noticia['fuente']}
Fecha: {noticia.get('fecha_noticia', '?')}
URL: {noticia.get('url', '')}

Resumen:
{noticia.get('resumen', '')}

Tickers preliminarmente detectados: {noticia.get('tickers_mencionados') or []}
Sectores preliminares: {noticia.get('sectores_mencionados') or []}

## TAREA
Analiza esta noticia con relación al portafolio del cliente. Responde SOLO con el JSON estructurado pedido en el system prompt."""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        txt = resp.content[0].text.strip()

        # Extraer JSON (puede venir con ```json wrapping)
        if "```" in txt:
            import re
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                txt = m.group(0)
        return json.loads(txt)
    except json.JSONDecodeError as e:
        print(f"    ⚠️ JSON inválido: {str(e)[:80]}")
        return None
    except Exception as e:
        print(f"    ❌ Error API: {str(e)[:100]}")
        return None


# ── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30,
                        help="Cuántas noticias procesar en este batch")
    parser.add_argument("--min-relevancia", type=int, default=25,
                        help="Score preliminar mínimo para gastar tokens AI")
    args = parser.parse_args()

    print("=" * 60)
    print("🧠 AI ANALYST — Procesando noticias con Claude")
    print("=" * 60)

    api_key = get_api_key()
    if not api_key:
        print("\n❌ Falta ANTHROPIC_API_KEY. Configúrala en .env o GitHub Secrets.")
        print("   Sin esto el análisis AI no funciona.")
        sys.exit(1)

    try:
        from anthropic import Anthropic
    except ImportError:
        print("\n❌ Falta el paquete anthropic. Corre: pip install anthropic")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    sb = get_client()

    # 1. Cargar contexto de cartera (1 vez por ejecución)
    print("\n📊 Cargando contexto de cartera...")
    portfolio_ctx = load_portfolio_context()

    # 2. Noticias pendientes con relevancia preliminar suficiente
    print(f"\n🔎 Buscando noticias pendientes (relevancia ≥ {args.min_relevancia})...")
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
        print("✅ Nada pendiente.")
        return

    # 3. Procesar cada noticia
    ok = err = 0
    for i, n in enumerate(noticias, 1):
        print(f"[{i}/{len(noticias)}] {n['titulo'][:70]}...")
        analisis = analyze_news_item(client, n, portfolio_ctx)

        if not analisis:
            err += 1
            continue

        # Validar keys mínimos
        required = {"relevancia_pct", "tipo", "confianza_senal", "resumen_esp"}
        if not required.issubset(analisis.keys()):
            print(f"    ⚠️ Faltan campos: {required - set(analisis.keys())}")
            err += 1
            continue

        try:
            # Insertar análisis
            sb.table("market_intelligence").insert({
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
            }).execute()

            # Marcar noticia como procesada
            sb.table("market_news").update({"procesado_ai": True}).eq("id", n["id"]).execute()
            ok += 1
            print(f"    ✅ {analisis['tipo']:12s} relev:{analisis['relevancia_pct']:>3} señal:{analisis['confianza_senal']}")
        except Exception as e:
            print(f"    ❌ DB error: {str(e)[:100]}")
            err += 1

    print(f"\n{'='*60}")
    print(f"✅ Procesadas: {ok}")
    print(f"❌ Errores:    {err}")


if __name__ == "__main__":
    main()
