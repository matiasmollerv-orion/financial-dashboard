# ============================================================
# REPORT BUILDER v2 — Email diario limpio y enfocado
#
# Estructura del email:
#   1. Brief header (mercado + resumen)
#   2. Max 5 alert cards (del daily_brief JSON)
#   3. Portfolio snapshot compacto
#   4. Ruido filtrado (1 linea)
#
# NO incluye:
#   - Docenas de alertas de concentracion/drawdown/volatilidad
#   - Lista larga de noticias sin priorizar
#   - Informacion que no es accionable
#
# Output: (subject, html_body, text_body)
# ============================================================

import sys, os, json
from datetime import datetime, timezone, timedelta, date
from typing import Optional
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import pandas as pd
from database.supabase_client import get_client


USD_CLP = 901.76


# ── Colores ─────────────────────────────────────────────────
COLORS = {
    "bg":          "#0e1117",
    "card":        "#1e2130",
    "border":      "#2d3250",
    "text":        "#ccd6f6",
    "text_dim":    "#8892b0",
    "primary":     "#4e79a7",
    "green":       "#2ecc71",
    "red":         "#e74c3c",
    "yellow":      "#f39c12",
    "purple":      "#9c75d8",
}

TIPO_COLOR = {
    "COMPRAR":      "#2ecc71",
    "VENDER":       "#e74c3c",
    "MONITOREAR":   "#f39c12",
    "RECORDATORIO": "#4e79a7",
    "RIESGO":       "#e74c3c",
}

TIPO_ICON = {
    "COMPRAR":      "🟢",
    "VENDER":       "🔴",
    "MONITOREAR":   "🟡",
    "RECORDATORIO": "🔵",
    "RIESGO":       "⚠️",
}

URGENCIA_STYLE = {
    "HOY":          ("font-weight:700; color:#e74c3c;", "HOY"),
    "ESTA SEMANA":  ("font-weight:600; color:#f39c12;", "ESTA SEMANA"),
    "PROXIMO MES":  ("font-weight:400; color:#8892b0;", "PROXIMO MES"),
}


# ── Loaders ─────────────────────────────────────────────────
def _safe_query(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if any(s in msg for s in ["not find the table", "pgrst205", "does not exist", "relation"]):
                print(f"  Tabla no existe ({fn.__name__}). Corre intelligence/schema.sql.")
                if "brief" in fn.__name__:
                    return {}
                return pd.DataFrame()
            raise
    return wrapper


@_safe_query
def load_daily_brief_json() -> dict:
    """Carga el brief JSON estructurado (guardado en metricas.brief_json)."""
    sb = get_client()
    r = (sb.table("portfolio_alerts")
           .select("mensaje,metricas,fecha_alerta")
           .eq("categoria", "daily_brief")
           .order("fecha_alerta", desc=True)
           .limit(1)
           .execute())
    if not r.data:
        return {}

    row = r.data[0]
    metricas = row.get("metricas") or {}

    # Try to get structured JSON from metricas
    if isinstance(metricas, dict) and "brief_json" in metricas:
        return metricas["brief_json"]

    # Fallback: return raw message
    return {"resumen_mercado": "", "alertas": [], "mensaje_raw": row.get("mensaje", "")}


@_safe_query
def load_raw_opportunity_alerts(max_alerts: int = 5) -> list:
    """Fallback: carga alertas crudas del opportunity_detector cuando no hay daily_brief AI."""
    sb = get_client()
    actionable_cats = [
        "oportunidad_dip", "watchlist_entry", "watchlist_tier2", "accion_pendiente",
    ]
    all_alerts = []
    for cat in actionable_cats:
        try:
            r = (sb.table("portfolio_alerts")
                    .select("*")
                    .eq("activo_alerta", True)
                    .eq("categoria", cat)
                    .order("fecha_alerta", desc=True)
                    .limit(10)
                    .execute())
            all_alerts.extend(r.data)
        except Exception:
            pass

    if not all_alerts:
        return []

    # Sort by severity and take top N
    sev_order = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "info": 4}
    all_alerts.sort(key=lambda a: sev_order.get((a.get("severidad") or "info").lower(), 99))

    # Convert to brief-compatible format
    result = []
    cat_to_tipo = {
        "oportunidad_dip": "COMPRAR",
        "watchlist_entry": "COMPRAR",
        "watchlist_tier2": "MONITOREAR",
        "accion_pendiente": "RECORDATORIO",
        "momentum_warning": "MONITOREAR",
    }
    for i, a in enumerate(all_alerts[:max_alerts], 1):
        metricas = a.get("metricas") or {}
        result.append({
            "prioridad": i,
            "tipo": cat_to_tipo.get(a.get("categoria", ""), "MONITOREAR"),
            "ticker": a.get("activo", "?"),
            "titulo": a.get("titulo", ""),
            "detalle": a.get("mensaje", ""),
            "monto_sugerido": None,
            "urgencia": "ESTA SEMANA" if a.get("severidad") in ("critica", "alta") else "PROXIMO MES",
        })

    return result


def load_portfolio_snapshot() -> dict:
    sb = get_client()
    r = sb.table("cartera_actual").select("*").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return {}
    for c in ["cantidad", "precio_compra", "precio_actual"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["valor_usd"] = df["cantidad"] * df["precio_actual"]
    df["costo_usd"] = df["cantidad"] * df["precio_compra"]
    df["valor_clp"] = df.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP, axis=1
    )
    df["costo_clp"] = df.apply(
        lambda r: r["costo_usd"] if r.get("moneda") == "CLP" else r["costo_usd"] * USD_CLP, axis=1
    )
    import numpy as np
    df["retorno_pct"] = np.where(
        df["precio_compra"] > 0,
        ((df["precio_actual"] - df["precio_compra"]) / df["precio_compra"] * 100).round(2),
        np.nan,
    )

    df_rankable = df[
        df["retorno_pct"].notna() &
        (df["valor_clp"] > 100_000)
    ].copy()

    total = df["valor_clp"].sum()
    total_costo = df["costo_clp"].sum()
    ganancia = total - total_costo
    ret_pct = (ganancia / total_costo * 100) if total_costo else 0

    return {
        "total_clp":      total,
        "total_costo":    total_costo,
        "ganancia":       ganancia,
        "retorno_pct":    ret_pct,
        "n_positions":    len(df),
        "top_gainers":    df_rankable.nlargest(3, "retorno_pct")[["ticker", "retorno_pct", "valor_clp"]].to_dict("records"),
        "top_losers":     df_rankable.nsmallest(3, "retorno_pct")[["ticker", "retorno_pct", "valor_clp"]].to_dict("records"),
    }


# ── Formato ─────────────────────────────────────────────────
def fmt_clp(v):
    try:
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.0f}".replace(",", ".")
    except Exception:
        return "-"


def fmt_pct(v):
    try:
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.2f}%"
    except Exception:
        return "-"


# ── HTML Builders ───────────────────────────────────────────
def _alert_card(alert: dict) -> str:
    """Render a single alert card from brief JSON."""
    tipo = alert.get("tipo", "MONITOREAR").upper()
    color = TIPO_COLOR.get(tipo, "#888")
    icon = TIPO_ICON.get(tipo, "📌")
    ticker = alert.get("ticker", "")
    titulo = alert.get("titulo", "")
    detalle = alert.get("detalle", "")
    monto = alert.get("monto_sugerido") or ""
    urgencia = alert.get("urgencia", "")
    prioridad = alert.get("prioridad", "?")

    urg_style, urg_label = URGENCIA_STYLE.get(urgencia, ("color:#8892b0;", urgencia))

    monto_html = ""
    if monto:
        monto_html = f"""
        <span style="background:{color}15; color:{color}; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600;">
          {monto}
        </span>"""

    urgencia_html = ""
    if urgencia:
        urgencia_html = f"""
        <span style="{urg_style} font-size:11px; padding:2px 8px; border-radius:10px; background:{color}11;">
          {urg_label}
        </span>"""

    return f"""
    <div style="background:{COLORS['card']}; padding:16px 18px; border-radius:10px; border-left:5px solid {color}; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="flex:1;">
          <span style="font-size:11px; color:{COLORS['text_dim']};">#{prioridad}</span>
          <span style="font-size:16px; font-weight:700; color:{COLORS['text']};">
            {icon} {ticker}
          </span>
          <span style="background:{color}22; color:{color}; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; margin-left:6px;">
            {tipo}
          </span>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          {monto_html}
          {urgencia_html}
        </div>
      </div>
      <div style="color:{COLORS['text']}; font-size:14px; font-weight:600; margin-top:8px;">
        {titulo}
      </div>
      <div style="color:{COLORS['text_dim']}; font-size:13px; margin-top:6px; line-height:1.5;">
        {detalle}
      </div>
    </div>"""


def _build_portfolio_compact(snap: dict) -> str:
    """Portfolio snapshot compacto (1 row)."""
    if not snap:
        return ""

    color_ret = COLORS["green"] if snap.get("retorno_pct", 0) >= 0 else COLORS["red"]

    # Top 3 gainers and losers inline
    gainers = " · ".join([
        f"<span style='color:{COLORS['green']};'>{g['ticker']} {fmt_pct(g['retorno_pct'])}</span>"
        for g in snap.get("top_gainers", [])
    ])
    losers = " · ".join([
        f"<span style='color:{COLORS['red']};'>{g['ticker']} {fmt_pct(g['retorno_pct'])}</span>"
        for g in snap.get("top_losers", [])
    ])

    return f"""
    <div style="background:{COLORS['card']}; padding:14px 18px; border-radius:10px; margin-top:20px;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <span style="color:{COLORS['text_dim']}; font-size:12px;">Patrimonio</span>
          <div style="color:{COLORS['text']}; font-size:18px; font-weight:700;">{fmt_clp(snap.get('total_clp', 0))}</div>
        </div>
        <div>
          <span style="color:{COLORS['text_dim']}; font-size:12px;">Retorno</span>
          <div style="color:{color_ret}; font-size:18px; font-weight:700;">{fmt_pct(snap.get('retorno_pct', 0))}</div>
        </div>
        <div>
          <span style="color:{COLORS['text_dim']}; font-size:12px;">Posiciones</span>
          <div style="color:{COLORS['text']}; font-size:18px; font-weight:700;">{snap.get('n_positions', 0)}</div>
        </div>
      </div>
      <div style="margin-top:10px; font-size:12px;">
        <span style="color:{COLORS['text_dim']};">Top:</span> {gainers}
        <span style="color:{COLORS['text_dim']}; margin-left:12px;">Bottom:</span> {losers}
      </div>
    </div>"""


def _fecha_es() -> str:
    """Fecha en espanol."""
    fecha_es = datetime.now().strftime("%A %d %B %Y")
    meses = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
             "May":"mayo","June":"junio","July":"julio","August":"agosto",
             "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
    dias = {"Monday":"lunes","Tuesday":"martes","Wednesday":"miercoles","Thursday":"jueves",
            "Friday":"viernes","Saturday":"sabado","Sunday":"domingo"}
    for k, v in meses.items():
        fecha_es = fecha_es.replace(k, v)
    for k, v in dias.items():
        fecha_es = fecha_es.replace(k, v)
    return fecha_es[0].upper() + fecha_es[1:]


# ── BUILD PRINCIPAL ─────────────────────────────────────────
def build_daily_report() -> tuple:
    """
    Construye el email diario.
    Returns: (subject, html_body, text_body)
    """
    print("Cargando datos para el email...")

    brief = load_daily_brief_json()
    snap = load_portfolio_snapshot()

    alertas = brief.get("alertas", [])
    resumen_mercado = brief.get("resumen_mercado", "")
    ruido = brief.get("ruido_filtrado", "")

    # Fallback: si no hay alertas del brief AI, usar alertas crudas del opportunity_detector
    if not alertas:
        alertas = load_raw_opportunity_alerts(max_alerts=5)
        if alertas:
            resumen_mercado = resumen_mercado or "Brief AI no disponible. Mostrando top 5 alertas del detector automatico."

    n_alertas = len(alertas)
    fecha = _fecha_es()

    # Subject
    if n_alertas > 0:
        first_tipo = alertas[0].get("tipo", "")
        first_ticker = alertas[0].get("ticker", "")
        subject = f"📊 {n_alertas} alertas | {first_tipo} {first_ticker} | {date.today().strftime('%d/%m')}"
    else:
        subject = f"✅ Sin novedades | {date.today().strftime('%d/%m')}"

    # Build alert cards HTML
    alert_cards = ""
    if alertas:
        alert_cards = "\n".join([_alert_card(a) for a in alertas])
    else:
        alert_cards = f"""
        <div style="background:{COLORS['card']}; padding:20px; border-radius:10px; text-align:center;">
          <div style="font-size:24px; margin-bottom:8px;">✅</div>
          <div style="color:{COLORS['text']}; font-size:14px;">Sin novedades relevantes hoy.</div>
          <div style="color:{COLORS['text_dim']}; font-size:12px; margin-top:4px;">El DCA semanal sigue su curso.</div>
        </div>"""

    # Ruido line
    ruido_html = ""
    if ruido:
        ruido_html = f"""
        <div style="margin-top:16px; padding:10px 14px; border-radius:8px; background:{COLORS['card']}; border-left:3px solid {COLORS['text_dim']};">
          <span style="color:{COLORS['text_dim']}; font-size:12px;">🔇 Ruido filtrado:</span>
          <span style="color:{COLORS['text_dim']}; font-size:12px;"> {ruido}</span>
        </div>"""

    # Fallback for old-format briefs
    raw_msg = brief.get("mensaje_raw", "")
    raw_html = ""
    if raw_msg and not alertas:
        raw_html = f"""
        <div style="background:{COLORS['card']}; padding:16px 20px; border-radius:10px; color:{COLORS['text']}; font-size:14px; line-height:1.6;">
          {raw_msg.replace(chr(10), '<br>')}
        </div>"""

    html = f"""
    <html><head><meta charset="utf-8"></head>
    <body style="background:{COLORS['bg']}; padding:24px 12px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:{COLORS['text']};">
      <div style="max-width:640px; margin:0 auto;">

        <!-- Header -->
        <h1 style="color:{COLORS['text']}; font-size:22px; margin:0 0 2px 0;">📊 Daily Brief</h1>
        <p style="color:{COLORS['text_dim']}; margin:0 0 16px 0; font-size:13px;">{fecha}</p>

        <!-- Market summary -->
        {'<div style="color:' + COLORS['text'] + '; font-size:14px; margin-bottom:18px; padding:10px 14px; background:' + COLORS['card'] + '; border-radius:8px;">' + resumen_mercado + '</div>' if resumen_mercado else ''}

        <!-- Alerts -->
        <div style="margin-bottom:6px;">
          <span style="color:{COLORS['text_dim']}; font-size:12px; text-transform:uppercase; letter-spacing:1px;">
            {'Alertas (' + str(n_alertas) + ')' if n_alertas else 'Estado'}
          </span>
        </div>
        {alert_cards}
        {raw_html}

        <!-- Noise -->
        {ruido_html}

        <!-- Portfolio compact -->
        {_build_portfolio_compact(snap)}

        <!-- Footer -->
        <div style="margin-top:24px; padding-top:14px; border-top:1px solid {COLORS['border']}; color:{COLORS['text_dim']}; font-size:11px; text-align:center;">
          Financial Dashboard · {date.today().isoformat()}<br>
          <a href="https://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/" style="color:{COLORS['primary']}; text-decoration:none;">
            Ver dashboard completo
          </a>
        </div>

      </div>
    </body></html>
    """

    # Text plain fallback
    text_lines = [f"Daily Brief — {fecha}", ""]
    if resumen_mercado:
        text_lines.append(f"Mercado: {resumen_mercado}\n")
    for a in alertas:
        text_lines.append(f"{a.get('prioridad','?')}. [{a.get('tipo','')}] {a.get('ticker','')}: {a.get('titulo','')}")
        text_lines.append(f"   {a.get('detalle','')}")
        if a.get("monto_sugerido"):
            text_lines.append(f"   Monto: {a['monto_sugerido']} | {a.get('urgencia','')}")
        text_lines.append("")
    if ruido:
        text_lines.append(f"Ruido: {ruido}")
    text_lines.append(f"\nPatrimonio: {fmt_clp(snap.get('total_clp', 0))} ({fmt_pct(snap.get('retorno_pct', 0))})")
    text_lines.append("\nhttps://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/")
    text = "\n".join(text_lines)

    return subject, html, text


# ── CLI ─────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--save", type=str, default=None,
                        help="Guardar HTML en archivo")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("DAILY EMAIL v2 — Generando reporte")
    print("=" * 60)

    subject, html, text = build_daily_report()

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML guardado en {args.save}. Abrelo en el navegador.")
        return

    if args.preview:
        print(f"\n--- SUBJECT ---\n{subject}")
        print(f"\n--- TEXT ---\n{text}")
        return

    from intelligence.email_sender import send_email
    ok = send_email(subject, html, text, dry_run=args.dry_run)
    print("OK" if ok else "FALLO")


if __name__ == "__main__":
    main()
