# ============================================================
# DISCOVERY REPORT v1 — Digest semanal de jugadores nuevos
#
# Separado del email diario a propósito (cadencia distinta, propósito
# distinto): esto NO son señales de compra, es "esto existe, evalúalo".
# Agrupa por fuente: 13F smart money, IPOs nuevos (S-1), menciones en
# noticias, menciones en newsletters de GBrain.
#
# Corre semanalmente desde discovery-weekly.yml, DESPUÉS de
# intelligence.discovery (que genera las alertas categoria=descubrimiento).
#
# CERO llamadas a la API de Anthropic.
#
# Uso:
#   python -m intelligence.discovery_report
#   python -m intelligence.discovery_report --dry-run
# ============================================================

import sys, argparse, warnings
from datetime import date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from database.supabase_client import get_client

COLORS = {
    "bg":       "#0e1117", "card": "#1e2130", "border": "#2d3250",
    "text":     "#ccd6f6", "text_dim": "#8892b0", "primary": "#4e79a7",
}

FUENTE_LABEL = {
    "13f":              ("📊", "13F Smart Money"),
    "ipo_s1":           ("🆕", "Nuevos IPOs (S-1)"),
    "noticias":         ("📰", "Menciones en noticias"),
    "gbrain_newsletter": ("📬", "Menciones en tus newsletters"),
}


def load_descubrimientos(days: int) -> list:
    sb = get_client()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        r = (sb.table("portfolio_alerts").select("*")
             .eq("categoria", "descubrimiento")
             .gte("fecha_alerta", cutoff)
             .order("fecha_alerta", desc=True)
             .execute())
        return r.data
    except Exception as e:
        print(f"Error leyendo descubrimientos: {e}")
        return []


def _card(a: dict) -> str:
    m = a.get("metricas") or {}
    fuente = m.get("fuente", "?")
    return f"""
    <div style="background:{COLORS['card']}; padding:14px 16px; border-radius:8px;
                margin-bottom:8px; border-left:3px solid {COLORS['primary']};">
      <div style="color:{COLORS['text']}; font-size:14px; font-weight:600; margin-bottom:4px;">
        {a.get('titulo', '?')}
      </div>
      <div style="color:{COLORS['text_dim']}; font-size:13px; line-height:1.5;">
        {a.get('mensaje', '')}
      </div>
      <div style="color:{COLORS['text_dim']}; font-size:12px; margin-top:6px;">
        {a.get('sugerencia', '')}
      </div>
    </div>"""


def build_report(days: int) -> tuple:
    descubrimientos = load_descubrimientos(days)
    fecha = date.today().strftime("%d/%m/%Y")

    if not descubrimientos:
        subject = f"🔭 Descubrimientos semanales — sin novedades ({fecha})"
        html = f"""
        <html><body style="background:{COLORS['bg']}; padding:24px; font-family:-apple-system,sans-serif;">
          <div style="max-width:600px; margin:0 auto; color:{COLORS['text']};">
            <h2>🔭 Descubrimientos de la semana</h2>
            <p style="color:{COLORS['text_dim']};">Sin jugadores nuevos detectados esta semana
            en 13F, IPOs, noticias o newsletters.</p>
          </div>
        </body></html>"""
        return subject, html, "Sin descubrimientos esta semana."

    por_fuente = {}
    for a in descubrimientos:
        m = a.get("metricas") or {}
        fuente = m.get("fuente", "otro")
        por_fuente.setdefault(fuente, []).append(a)

    n = len(descubrimientos)
    subject = f"🔭 {n} descubrimientos esta semana ({fecha})"

    secciones = ""
    orden = ["13f", "ipo_s1", "noticias", "gbrain_newsletter"]
    for fuente in orden:
        items = por_fuente.get(fuente, [])
        if not items:
            continue
        emoji, label = FUENTE_LABEL.get(fuente, ("•", fuente))
        cards = "\n".join(_card(a) for a in items[:10])
        secciones += f"""
        <div style="margin-bottom:20px;">
          <div style="color:{COLORS['text_dim']}; font-size:12px; text-transform:uppercase;
                      letter-spacing:1px; margin-bottom:8px;">
            {emoji} {label} ({len(items)})
          </div>
          {cards}
        </div>"""

    html = f"""
    <html><head><meta charset="utf-8"></head>
    <body style="background:{COLORS['bg']}; padding:24px 12px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <div style="max-width:640px; margin:0 auto;">
        <h1 style="color:{COLORS['text']}; font-size:22px; margin:0 0 2px 0;">🔭 Descubrimientos de la semana</h1>
        <p style="color:{COLORS['text_dim']}; margin:0 0 18px 0; font-size:13px;">{fecha}</p>
        <p style="color:{COLORS['text_dim']}; font-size:13px; margin-bottom:20px;">
          Jugadores nuevos FUERA de tu watchlist — no son señales de compra, es
          "esto existe, evalúalo". Detectado en 13F de smart money, IPOs nuevos (S-1),
          noticias y tus newsletters de GBrain.
        </p>
        {secciones}
        <div style="margin-top:24px; padding-top:14px; border-top:1px solid {COLORS['border']};
                    color:{COLORS['text_dim']}; font-size:11px; text-align:center;">
          Financial Dashboard · Discovery Report · {fecha}
        </div>
      </div>
    </body></html>"""

    text = f"Descubrimientos de la semana ({fecha})\n\n" + "\n".join(
        f"[{(a.get('metricas') or {}).get('fuente', '?')}] {a['titulo']}\n  {a['mensaje']}\n"
        for a in descubrimientos
    )
    return subject, html, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=8,
                        help="Ventana de días a incluir (default 8, cubre la semana + margen)")
    args = parser.parse_args()

    print("=" * 60)
    print("DISCOVERY REPORT v1 — Digest semanal")
    print("=" * 60)

    subject, html, text = build_report(args.days)
    print(f"Subject: {subject}")

    if args.dry_run:
        print("DRY RUN — no se envía")
        return

    from intelligence.email_sender import send_email
    ok = send_email(subject, html, text, dry_run=False)
    print("✅ Enviado" if ok else "❌ Error al enviar")
    print("=" * 60)


if __name__ == "__main__":
    main()
