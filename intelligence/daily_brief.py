# ============================================================
# DAILY BRIEF v2 — Max 5 alertas accionables
#
# Consolida TODO (alertas de cartera, watchlist, noticias AI,
# acciones pendientes) y genera un brief de MAX 5 items
# priorizados y accionables.
#
# Filosofia:
#   - Una alerta NO es estar en rojo en una posicion
#   - Una alerta ES una oportunidad basada en news/mercado
#   - Watchlist + entry targets son prioridad
#   - Signal, not noise
#
# Uso: python -m intelligence.daily_brief
# ============================================================

import sys, os, json
from datetime import datetime, timezone, timedelta
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
from intelligence.ai_analyst import get_api_key, load_portfolio_context, MODEL

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"
MAX_ALERTS = 5


def load_watchlist_context_brief() -> str:
    """Version resumida del watchlist para el brief prompt."""
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            wl = yaml.safe_load(f)
    except FileNotFoundError:
        return ""

    lines = []

    # Solo lo accionable
    lines.append("ACCIONES PENDIENTES:")
    for item in wl.get("acciones_pendientes", []):
        lines.append(f"  - {item.get('accion','')} {item['ticker']} USD {item.get('monto_usd','?')} [{item.get('urgencia','')}]")

    lines.append("\nTIER 1 WATCHLIST (entry targets):")
    for item in wl.get("watchlist", {}).get("tier1", []):
        entry = item.get("entry_usd", "?")
        lines.append(f"  - {item['ticker']} target USD {entry}")

    return "\n".join(lines)


SYSTEM_BRIEF = """Eres el asesor de inversiones personal de tu cliente. Tu trabajo es entregar un Daily Brief con MAXIMO 5 alertas accionables.

REGLAS CRITICAS:
1. MAXIMO 5 alertas. Si hay menos de 5 cosas relevantes, entrega menos. "Sin novedades" es perfectamente valido.
2. Una alerta NO es simplemente que una posicion este en rojo. Eso es ruido.
3. Una alerta SI es:
   - Un DIP significativo en un ticker de alta conviccion (oportunidad de compra)
   - Un ticker del watchlist que llego a su entry target
   - Una noticia que crea una oportunidad o riesgo REAL
   - Una accion pendiente que necesita ejecutarse pronto
   - Un evento proximo (earnings, conferencia, 13F deadline) que requiere atencion
4. Prioriza OPORTUNIDADES sobre riesgos (el cliente quiere saber donde comprar, no donde perder).
5. Se directo. Nada de "podria ser interesante considerar". Di "COMPRAR", "MONITOREAR", "NO ACTUAR".
6. Si la unica novedad es que el mercado bajo 1%, eso es ruido. No alertes.

Formato EXACTO (respeta el JSON):

{
  "resumen_mercado": "1 linea del estado general del mercado hoy",
  "alertas": [
    {
      "prioridad": 1,
      "tipo": "COMPRAR" | "VENDER" | "MONITOREAR" | "RECORDATORIO" | "RIESGO",
      "ticker": "XXXX",
      "titulo": "Titulo corto y directo",
      "detalle": "2-3 lineas explicando por que y que hacer",
      "monto_sugerido": "USD XXX" o null,
      "urgencia": "HOY" | "ESTA SEMANA" | "PROXIMO MES"
    }
  ],
  "ruido_filtrado": "1 linea sobre que ignoraste hoy y por que"
}
"""


def generate_brief():
    api_key = get_api_key()
    if not api_key:
        print("Falta ANTHROPIC_API_KEY.")
        return None

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    sb = get_client()

    # 1. Portfolio context
    portfolio_ctx = load_portfolio_context()
    watchlist_ctx = load_watchlist_context_brief()

    # 2. Intelligence de ultimas 48h (wider window for better context)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    intel = (sb.table("market_intelligence")
               .select("*, market_news!inner(titulo,fuente,url,fecha_noticia)")
               .gte("fecha_analisis", cutoff)
               .order("relevancia_pct", desc=True)
               .limit(20)
               .execute())

    # 3. Alertas activas de oportunidad (NO las de health/concentracion/drawdown)
    actionable_cats = [
        "oportunidad_dip", "watchlist_entry", "watchlist_tier2",
        "accion_pendiente", "momentum_warning",
    ]
    alerts_data = []
    for cat in actionable_cats:
        try:
            r = (sb.table("portfolio_alerts")
                    .select("*")
                    .eq("activo_alerta", True)
                    .eq("categoria", cat)
                    .order("fecha_alerta", desc=True)
                    .limit(10)
                    .execute())
            alerts_data.extend(r.data)
        except Exception:
            pass

    # 4. Armar contexto para Claude
    intel_text = []
    for it in intel.data:
        n = it.get("market_news") or {}
        wl_info = ""
        raz = it.get("razonamiento", "")
        if "WATCHLIST:" in (raz or ""):
            wl_info = " | " + raz.split("WATCHLIST:")[1].strip()[:100]
        intel_text.append(
            f"- [{it.get('tipo','?').upper()}|senal:{it.get('confianza_senal','?')}|rel:{it.get('relevancia_pct',0)}] "
            f"{n.get('titulo','')[:120]} "
            f"-> {it.get('resumen_esp','')[:150]} "
            f"(accion: {it.get('accion_sugerida','—')}){wl_info}"
        )

    alert_text = []
    for a in alerts_data:
        alert_text.append(
            f"- [{a.get('severidad','?').upper()}|{a.get('categoria','?')}] "
            f"{a.get('activo','?')}: {a.get('titulo','')} — {a.get('sugerencia','')}"
        )

    # Check upcoming events
    events_text = _check_upcoming_events()

    user_msg = f"""## CARTERA
{portfolio_ctx}

## WATCHLIST Y ACCIONES PENDIENTES
{watchlist_ctx}

## ALERTAS DE OPORTUNIDAD ACTIVAS (detectadas por el sistema)
{chr(10).join(alert_text) if alert_text else "(sin alertas de oportunidad activas)"}

## NOTICIAS ANALIZADAS POR AI (ultimas 48h, top 20)
{chr(10).join(intel_text) if intel_text else "(sin noticias relevantes)"}

## EVENTOS PROXIMOS
{events_text}

## TAREA
Genera el Daily Brief para {datetime.now().strftime('%d %b %Y')}.
MAXIMO 5 alertas. Prioriza oportunidades de compra sobre riesgos.
Si no hay nada relevante, di que no hay novedades.
Responde SOLO con el JSON."""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_BRIEF,
            messages=[{"role": "user", "content": user_msg}],
        )
        txt = resp.content[0].text.strip()

        # Extract JSON
        if "```" in txt:
            import re
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                txt = m.group(0)

        brief_data = json.loads(txt)

        # Enforce max 5
        if "alertas" in brief_data and len(brief_data["alertas"]) > MAX_ALERTS:
            brief_data["alertas"] = brief_data["alertas"][:MAX_ALERTS]

        return brief_data

    except json.JSONDecodeError as e:
        print(f"JSON invalido del brief: {str(e)[:80]}")
        print(f"Raw: {txt[:500]}")
        return None
    except Exception as e:
        print(f"Error generando brief: {e}")
        return None


def _check_upcoming_events() -> str:
    """Revisa eventos proximos (conferencias, 13F deadlines)."""
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            wl = yaml.safe_load(f)
    except FileNotFoundError:
        return "(sin datos de eventos)"

    lines = []
    today = datetime.now()
    current_month = today.month

    # Conferencias este mes o el proximo
    for conf in wl.get("conferencias", []):
        mes = conf.get("mes", 0)
        if mes == current_month or mes == (current_month % 12) + 1:
            tickers = ", ".join(str(t) for t in conf.get("tickers", []))
            lines.append(f"- {conf['nombre']} (mes {mes}): {tickers}")

    # 13F deadlines proximos
    for f13 in wl.get("fechas_13f", []):
        deadline = f13.get("deadline", "")
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d")
            days_until = (dl - today).days
            if 0 <= days_until <= 30:
                funds = ", ".join(f.get("nombre", "") for f in wl.get("smart_money_funds", [])[:5])
                lines.append(f"- 13F deadline {f13['quarter']}: {deadline} ({days_until}d). Fondos: {funds}...")
        except ValueError:
            pass

    return "\n".join(lines) if lines else "(sin eventos proximos relevantes)"


def save_brief(brief_data: dict):
    """Guarda el brief estructurado en portfolio_alerts."""
    if not brief_data:
        return

    # Convert to readable text for storage
    lines = []
    lines.append(f"## Daily Brief {datetime.now().strftime('%d %b %Y')}")
    lines.append(f"\n**Mercado:** {brief_data.get('resumen_mercado', '—')}")

    alertas = brief_data.get("alertas", [])
    if alertas:
        lines.append(f"\n**{len(alertas)} alertas:**")
        for a in alertas:
            tipo = a.get("tipo", "?")
            ticker = a.get("ticker", "?")
            titulo = a.get("titulo", "")
            detalle = a.get("detalle", "")
            monto = a.get("monto_sugerido", "")
            urgencia = a.get("urgencia", "")
            lines.append(f"\n{a.get('prioridad', '?')}. [{tipo}] {ticker}: {titulo}")
            lines.append(f"   {detalle}")
            if monto:
                lines.append(f"   Monto: {monto} | Urgencia: {urgencia}")
    else:
        lines.append("\nSin novedades relevantes hoy.")

    ruido = brief_data.get("ruido_filtrado", "")
    if ruido:
        lines.append(f"\n**Ruido filtrado:** {ruido}")

    brief_text = "\n".join(lines)

    sb = get_client()
    try:
        sb.table("portfolio_alerts").insert({
            "categoria":   "daily_brief",
            "severidad":   "info",
            "activo":      "PORTFOLIO",
            "titulo":      f"Daily Brief {datetime.now().strftime('%Y-%m-%d')}",
            "mensaje":     brief_text,
            "metricas":    {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "n_alertas": len(alertas),
                "brief_json": brief_data,
            },
            "sugerencia":  "Revisa el brief en la pestana Inteligencia.",
        }).execute()
        print("Brief guardado en portfolio_alerts")
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg:
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                sb.table("portfolio_alerts").update({
                    "mensaje": brief_text,
                    "metricas": {
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "n_alertas": len(alertas),
                        "brief_json": brief_data,
                    },
                }).eq("categoria", "daily_brief").eq("activo", "PORTFOLIO").gte(
                    "fecha_alerta", today
                ).execute()
                print("Brief actualizado (ya existia uno de hoy)")
            except Exception as e2:
                print(f"Error actualizando: {e2}")
        else:
            print(f"Error guardando brief: {e}")


def main():
    print("=" * 60)
    print("DAILY BRIEF v2 — Max 5 alertas accionables")
    print("=" * 60)

    brief_data = generate_brief()
    if not brief_data:
        print("No se pudo generar brief.")
        return

    # Print summary
    alertas = brief_data.get("alertas", [])
    print(f"\nMercado: {brief_data.get('resumen_mercado', '—')}")
    print(f"Alertas: {len(alertas)}")
    for a in alertas:
        print(f"  {a.get('prioridad', '?')}. [{a.get('tipo', '?'):12s}] "
              f"{a.get('ticker', '?'):8s} {a.get('titulo', '')}")
    print(f"Ruido filtrado: {brief_data.get('ruido_filtrado', '—')}")
    print("-" * 60)

    save_brief(brief_data)


if __name__ == "__main__":
    main()
