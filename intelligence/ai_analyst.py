# ============================================================
# AI ANALYST v3 — Analisis de noticias con contexto de watchlist
#
# Procesa noticias pendientes (market_news.procesado_ai = false)
# y genera analisis estructurado en market_intelligence.
#
# v3 (2026-08-22) — auditoria de costo API, cambios:
#   1. PROMPT CACHING: SYSTEM_PROMPT + contexto de cartera/watchlist
#      (estatico dentro de una corrida, se repetia en cada llamada)
#      ahora va en un bloque system con cache_control ephemeral.
#   2. BATCH API: en vez de llamadas sincronas en loop, se sube UN
#      batch con todas las noticias del dia (50% mas barato, se puede
#      combinar con caching). Como la Batch API es asincronica
#      (minutos a 24h), el script se separa en dos modos:
#        --submit   sube el batch y guarda el batch_id en ai_batches
#        --collect  revisa batches pendientes y procesa los que ya
#                   terminaron
#      IMPORTANTE: esto significa que el analisis de una noticia YA NO
#      esta listo en la misma corrida que la sube. Requiere DOS pasos
#      de workflow (ej. --submit en la corrida de la mañana, --collect
#      en una corrida posterior) en vez de uno solo. Si se necesita el
#      resultado garantizado el mismo dia, hay que correr --collect
#      mas de una vez (es idempotente: si el batch no ha terminado,
#      no hace nada y no cobra de mas).
#   3. DEDUP: antes de armar el batch, se agrupan noticias casi-
#      identicas (mismo evento, > 1 fuente) por similitud de titulo.
#      Solo se manda UNA a la API; el resto se marca procesada
#      copiando su analisis (sin gastar tokens extra).
#
# Requiere: ANTHROPIC_API_KEY
# Uso:
#   python -m intelligence.ai_analyst --submit --limit 30
#   python -m intelligence.ai_analyst --collect
# ============================================================

import sys, os, json, argparse, time, difflib
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

# Umbral de similitud de titulo para considerar dos noticias "el mismo evento".
# SequenceMatcher.ratio() sobre titulos normalizados (minuscula, sin puntuacion).
DEDUP_SIMILARITY_THRESHOLD = 0.72


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

    lines.append("PLAN RECURRENTE (DCA semanal):")
    for item in wl.get("recurrente", []):
        lines.append(f"  - {item['ticker']:8s} USD {item['usd_sem']}/sem  [{item.get('bucket','')}] {item.get('tesis','')}")

    lines.append("\nWATCHLIST TIER 1 (alta conviccion, entry targets):")
    for item in wl.get("watchlist", {}).get("tier1", []):
        entry = item.get("entry_usd", "?")
        lines.append(f"  - {item['ticker']:8s} entry USD {entry}  [{item.get('bucket','')}] {item.get('tesis','')}")

    lines.append("\nWATCHLIST TIER 2 (monitoreo activo):")
    for item in wl.get("watchlist", {}).get("tier2", []):
        lines.append(f"  - {item['ticker']:8s} [{item.get('bucket','')}] {item.get('tesis','')}")

    lines.append("\nBUCKETS TEMATICOS (areas de interes):")
    for b in wl.get("buckets", []):
        lines.append(f"  - {b['nombre']}: {', '.join(b.get('keywords', []))}")

    lines.append("\nACCIONES PENDIENTES:")
    for item in wl.get("acciones_pendientes", []):
        lines.append(f"  - {item.get('accion','')} {item['ticker']} USD {item.get('monto_usd','?')} [{item.get('urgencia','')}] {item.get('nota','')}")

    return "\n".join(lines)


# ── PROMPT v2 (sin cambios de contenido, solo de como se envia) ─
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


def build_system_blocks(portfolio_ctx: str, watchlist_ctx: str) -> list:
    """
    Bloque system con cache_control. TODO lo que va antes del breakpoint
    (SYSTEM_PROMPT + cartera + watchlist) es identico en cada llamada de
    esta corrida -> se cachea como una unidad. Solo la noticia especifica
    va en el mensaje user, fuera del cache.
    """
    contexto_estatico = (
        f"## CARTERA DEL CLIENTE\n{portfolio_ctx}\n\n"
        f"## WATCHLIST Y PLAN DE INVERSIONES\n{watchlist_ctx}"
    )
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": contexto_estatico,
         "cache_control": {"type": "ephemeral"}},
    ]


def build_user_msg(noticia: dict) -> str:
    return f"""## NOTICIA A ANALIZAR
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


# ── DEDUP ─────────────────────────────────────────────────────
def _normalizar_titulo(t: str) -> str:
    import re
    t = (t or "").lower()
    t = re.sub(r"[^\w\sáéíóúñ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def agrupar_duplicados(noticias: list) -> tuple:
    """
    Agrupa noticias casi-identicas (mismo evento, > 1 fuente) por
    similitud de titulo. Retorna (a_analizar, duplicados) donde
    duplicados es {noticia_dup: noticia_canonica} para copiar el
    analisis sin llamar a la API de nuevo.
    """
    titulos_norm = [_normalizar_titulo(n["titulo"]) for n in noticias]
    usados = set()
    a_analizar = []
    duplicados = {}

    for i, n in enumerate(noticias):
        if i in usados:
            continue
        a_analizar.append(n)
        usados.add(i)
        for j in range(i + 1, len(noticias)):
            if j in usados:
                continue
            ratio = difflib.SequenceMatcher(None, titulos_norm[i], titulos_norm[j]).ratio()
            if ratio >= DEDUP_SIMILARITY_THRESHOLD:
                duplicados[noticias[j]["id"]] = n
                usados.add(j)

    return a_analizar, duplicados


def _parse_json_response(txt: str):
    txt = txt.strip()
    if "```" in txt:
        import re
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            txt = m.group(0)
    return json.loads(txt)


def _row_from_analisis(noticia_id: int, analisis: dict) -> dict:
    row = {
        "noticia_id":           noticia_id,
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
    wl_rel = analisis.get("watchlist_relevance")
    if wl_rel and wl_rel != "null" and str(wl_rel).lower() != "none":
        row["razonamiento"] = (row.get("razonamiento") or "") + f"\n\nWATCHLIST: {wl_rel}"
    return row


# ── SUBMIT ────────────────────────────────────────────────────
def submit_batch(limit: int, min_relevancia: int):
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

    print("Cargando contexto de cartera y watchlist (1 vez, se cachea)...")
    portfolio_ctx = load_portfolio_context()
    watchlist_ctx = load_watchlist_context()
    system_blocks = build_system_blocks(portfolio_ctx, watchlist_ctx)

    print(f"Buscando noticias pendientes (relevancia >= {min_relevancia})...")
    r = (sb.table("market_news")
           .select("*")
           .eq("procesado_ai", False)
           .gte("relevancia_preliminar", min_relevancia)
           .order("relevancia_preliminar", desc=True)
           .order("fecha_noticia", desc=True)
           .limit(limit)
           .execute())
    noticias = r.data
    print(f"   {len(noticias)} noticias encontradas")

    if not noticias:
        print("Nada pendiente.")
        return

    a_analizar, duplicados = agrupar_duplicados(noticias)
    print(f"   {len(a_analizar)} a analizar via API, {len(duplicados)} duplicados (se copia analisis, 0 tokens extra)")

    # Duplicados: se resuelven despues de que el canonico tenga analisis
    # (en collect_batch), asi que por ahora solo dejamos constancia de
    # cual es cual. Se guarda junto al batch para no perder el mapeo.
    dup_map = {str(dup_id): str(canon["id"]) for dup_id, canon in duplicados.items()}

    requests = []
    for n in a_analizar:
        requests.append({
            "custom_id": str(n["id"]),
            "params": {
                "model": MODEL,
                "max_tokens": 1500,
                "system": system_blocks,
                "messages": [{"role": "user", "content": build_user_msg(n)}],
            },
        })

    print(f"Subiendo batch de {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    print(f"   batch_id = {batch.id}  (status: {batch.processing_status})")

    sb.table("ai_batches").insert({
        "batch_id":     batch.id,
        "n_requests":   len(requests),
        "noticia_ids":  {"a_analizar": [str(n["id"]) for n in a_analizar], "duplicados": dup_map},
        "status":       "submitted",
    }).execute()

    print("Batch registrado en ai_batches. Correr --collect mas tarde para procesar resultados.")


# ── COLLECT ───────────────────────────────────────────────────
def collect_batches(max_wait_checks: int = 1):
    api_key = get_api_key()
    if not api_key:
        print("\nFalta ANTHROPIC_API_KEY.")
        sys.exit(1)
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    sb = get_client()

    r = sb.table("ai_batches").select("*").eq("status", "submitted").execute()
    pendientes = r.data
    if not pendientes:
        print("No hay batches pendientes.")
        return

    print(f"{len(pendientes)} batch(es) pendiente(s) de recolectar.")

    for reg in pendientes:
        batch_id = reg["batch_id"]
        b = client.messages.batches.retrieve(batch_id)
        print(f"\nbatch {batch_id}: status={b.processing_status}")

        if b.processing_status != "ended":
            print("   todavia procesando, se revisa en la proxima corrida de --collect.")
            continue

        dup_map = (reg.get("noticia_ids") or {}).get("duplicados", {})
        analisis_por_noticia = {}
        ok = err = 0

        for result in client.messages.batches.results(batch_id):
            noticia_id = int(result.custom_id)
            if result.result.type != "succeeded":
                print(f"   [{noticia_id}] fallo en el batch: {result.result.type}")
                err += 1
                continue
            try:
                txt = result.result.message.content[0].text
                analisis = _parse_json_response(txt)
                required = {"relevancia_pct", "tipo", "confianza_senal", "resumen_esp"}
                if not required.issubset(analisis.keys()):
                    print(f"   [{noticia_id}] faltan campos: {required - set(analisis.keys())}")
                    err += 1
                    continue
                analisis_por_noticia[noticia_id] = analisis
                sb.table("market_intelligence").insert(_row_from_analisis(noticia_id, analisis)).execute()
                sb.table("market_news").update({"procesado_ai": True}).eq("id", noticia_id).execute()
                ok += 1
            except (json.JSONDecodeError, IndexError, AttributeError) as e:
                print(f"   [{noticia_id}] error parseando respuesta: {str(e)[:100]}")
                err += 1

        # Duplicados: copiar el analisis del canonico (0 tokens extra)
        dup_ok = 0
        for dup_id_str, canon_id_str in dup_map.items():
            canon_analisis = analisis_por_noticia.get(int(canon_id_str))
            if not canon_analisis:
                continue
            try:
                row = _row_from_analisis(int(dup_id_str), canon_analisis)
                row["razonamiento"] = (row.get("razonamiento") or "") + \
                    f"\n\n(Duplicado de noticia #{canon_id_str}, mismo analisis, sin costo API adicional.)"
                sb.table("market_intelligence").insert(row).execute()
                sb.table("market_news").update({"procesado_ai": True}).eq("id", int(dup_id_str)).execute()
                dup_ok += 1
            except Exception as e:
                print(f"   [dup {dup_id_str}] error: {str(e)[:100]}")

        sb.table("ai_batches").update({
            "status": "collected",
            "collected_at": datetime.utcnow().isoformat(),
        }).eq("batch_id", batch_id).execute()

        print(f"   Procesadas: {ok} | Duplicados copiados: {dup_ok} | Errores: {err}")


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true", help="Sube un batch nuevo con noticias pendientes")
    parser.add_argument("--collect", action="store_true", help="Recolecta resultados de batches ya terminados")
    parser.add_argument("--limit", type=int, default=30,
                        help="Cuantas noticias procesar en este batch (solo con --submit)")
    parser.add_argument("--min-relevancia", type=int, default=25,
                        help="Score preliminar minimo para gastar tokens AI")
    args = parser.parse_args()

    print("=" * 60)
    print("AI ANALYST v3 — Batch API + prompt caching + dedup")
    print("=" * 60)

    if not args.submit and not args.collect:
        print("\nEspecifica --submit y/o --collect.")
        sys.exit(1)

    if args.submit:
        submit_batch(args.limit, args.min_relevancia)
    if args.collect:
        collect_batches()


if __name__ == "__main__":
    main()
