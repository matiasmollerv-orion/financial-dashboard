# ============================================================
# DAILY BRIEF — Asesor personalizado diario
# Consolida noticias analizadas + alertas de cartera en un
# resumen ejecutivo accionable, generado por Claude.
#
# Uso: python -m intelligence.daily_brief
# ============================================================

import sys, os, json
from datetime import datetime, timezone, timedelta
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
from database.supabase_client import get_client
from intelligence.ai_analyst import get_api_key, load_portfolio_context, MODEL


SYSTEM_BRIEF = """Eres el asesor de inversiones personal de tu cliente. Cada día le entregas un Daily Brief: un resumen ejecutivo claro, directo, sin paja, que le permita tomar decisiones en 2 minutos.

Tu tono: amigable pero profesional. Como un colega senior que respeta su tiempo. Nada de descargos legales innecesarios. Nada de "podría ser interesante considerar evaluar". Sé concreto.

Estructura SIEMPRE así (en este formato exacto, con emojis):

## 🌅 Daily Brief — [Fecha]

**📊 Estado general:** [1-2 líneas: ¿cómo va la cartera hoy en términos generales?]

**🎯 Top 3 prioridades hoy:**
1. [acción concreta o noticia más importante]
2. [...]
3. [...]

**⚠️ Riesgos activos:**
- [Cada riesgo en una línea con acción]

**💡 Oportunidades:**
- [Cada oportunidad en una línea]

**🔇 Filtrado como ruido:** [breve mención de lo que NO importa hoy a pesar de ser tendencia]

Termina con una recomendación concreta de **qué revisar hoy** (no más de 1-2 cosas).
"""


def generate_brief():
    api_key = get_api_key()
    if not api_key:
        print("❌ Falta ANTHROPIC_API_KEY.")
        return None

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    sb = get_client()

    # 1. Cartera
    portfolio_ctx = load_portfolio_context()

    # 2. Intelligence de últimas 24h
    ayer = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    intel = (sb.table("market_intelligence")
               .select("*, market_news!inner(titulo,fuente,url,fecha_noticia)")
               .gte("fecha_analisis", ayer)
               .order("relevancia_pct", desc=True)
               .limit(15)
               .execute())

    # 3. Alertas activas de cartera
    alerts = (sb.table("portfolio_alerts")
                .select("*")
                .eq("activo_alerta", True)
                .order("severidad")
                .limit(20)
                .execute())

    # 4. Armar contexto
    intel_text = []
    for it in intel.data:
        n = it.get("market_news") or {}
        intel_text.append(
            f"- [{it.get('tipo','?').upper()}|{it.get('confianza_senal','?')}|rel:{it.get('relevancia_pct',0)}] "
            f"{n.get('titulo','')[:120]} "
            f"→ {it.get('resumen_esp','')[:150]} "
            f"(acción sugerida: {it.get('accion_sugerida','—')})"
        )

    alert_text = []
    for a in alerts.data:
        alert_text.append(
            f"- [{a.get('severidad','?').upper()}|{a.get('categoria','?')}] "
            f"{a.get('activo','?')}: {a.get('titulo','')} — {a.get('sugerencia','')}"
        )

    user_msg = f"""## CARTERA
{portfolio_ctx}

## NOTICIAS ANALIZADAS (últimas 24h, top 15 por relevancia)
{chr(10).join(intel_text) if intel_text else "(sin noticias relevantes hoy)"}

## ALERTAS ACTIVAS DE CARTERA
{chr(10).join(alert_text) if alert_text else "(sin alertas activas)"}

Genera el Daily Brief para hoy {datetime.now().strftime('%d %b %Y')}."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_BRIEF,
        messages=[{"role": "user", "content": user_msg}],
    )
    brief_text = resp.content[0].text.strip()
    return brief_text


def save_brief(brief_text: str):
    """Guarda el brief como una fila especial en portfolio_alerts (categoria='daily_brief')."""
    if not brief_text:
        return
    sb = get_client()
    try:
        sb.table("portfolio_alerts").insert({
            "categoria":   "daily_brief",
            "severidad":   "info",
            "activo":      "PORTFOLIO",
            "titulo":      f"Daily Brief {datetime.now().strftime('%Y-%m-%d')}",
            "mensaje":     brief_text,
            "metricas":    {"generated_at": datetime.now(timezone.utc).isoformat()},
            "sugerencia":  "Revisa el brief completo en la pestaña Inteligencia.",
        }).execute()
        print("✅ Brief guardado en portfolio_alerts")
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg:
            # Ya existe brief de hoy → actualizar
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                sb.table("portfolio_alerts").update({
                    "mensaje": brief_text,
                    "metricas": {"updated_at": datetime.now(timezone.utc).isoformat()},
                }).eq("categoria", "daily_brief").eq("activo", "PORTFOLIO").gte(
                    "fecha_alerta", today
                ).execute()
                print("✅ Brief actualizado (ya existía uno de hoy)")
            except Exception as e2:
                print(f"❌ Error actualizando: {e2}")
        else:
            print(f"❌ Error guardando brief: {e}")


def main():
    print("=" * 60)
    print("📰 DAILY BRIEF — Generando resumen ejecutivo")
    print("=" * 60)

    brief = generate_brief()
    if not brief:
        print("⚠️ No se pudo generar brief.")
        return

    print("\n" + "─" * 60)
    print(brief)
    print("─" * 60 + "\n")

    save_brief(brief)


if __name__ == "__main__":
    main()
