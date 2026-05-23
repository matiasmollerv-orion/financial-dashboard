# ============================================================
# REPORT BUILDER — Construye el email diario HTML
#
# Combina:
#   1. Alertas de cartera activas (portfolio_alerts)
#   2. Daily Brief AI (si está disponible)
#   3. Noticias categorizadas últimas 24h (market_news/market_intelligence)
#   4. Portfolio status (top movers, P&L)
#
# Output: (subject, html_body, text_body)
# ============================================================

import sys, os, json
from datetime import datetime, timezone, timedelta, date
from typing import Optional
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
from database.supabase_client import get_client


USD_CLP = 901.76


# ── Colores (consistentes con dashboard) ─────────────────────
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

SEV_COLOR = {
    "critica": "#8b0000", "alta": "#e74c3c", "media": "#f39c12",
    "baja":    "#3498db", "info": "#95a5a6",
}

TIPO_COLOR = {
    "riesgo":      "#e74c3c",
    "oportunidad": "#2ecc71",
    "neutro":      "#95a5a6",
}


# ── Loaders (defensivos, retornan vacío si la tabla no existe) ───
def _safe_query(fn):
    """Decorator que captura errores 'table not found' y retorna df/str vacío."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if any(s in msg for s in ["not find the table", "pgrst205", "does not exist", "relation"]):
                print(f"  ⚠️ Tabla no existe ({fn.__name__}). Skipping. Corre intelligence/schema.sql en Supabase.")
                # Determinar tipo de retorno
                if "brief" in fn.__name__:
                    return ""
                return pd.DataFrame()
            raise
    return wrapper


@_safe_query
def load_active_alerts() -> pd.DataFrame:
    sb = get_client()
    r = (sb.table("portfolio_alerts")
           .select("*")
           .eq("activo_alerta", True)
           .neq("categoria", "daily_brief")
           .order("severidad")
           .limit(50)
           .execute())
    return pd.DataFrame(r.data)


@_safe_query
def load_daily_brief() -> str:
    sb = get_client()
    r = (sb.table("portfolio_alerts")
           .select("mensaje,fecha_alerta")
           .eq("categoria", "daily_brief")
           .order("fecha_alerta", desc=True)
           .limit(1)
           .execute())
    return (r.data[0]["mensaje"] if r.data else "")


@_safe_query
def load_intel_news(hours: int = 24, max_total: int = 15) -> pd.DataFrame:
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    intel = (sb.table("market_intelligence").select("*")
               .gte("fecha_analisis", cutoff)
               .order("relevancia_pct", desc=True)
               .limit(max_total).execute())
    if not intel.data:
        return pd.DataFrame()
    df_i = pd.DataFrame(intel.data)

    ids = df_i["noticia_id"].dropna().unique().tolist()
    if not ids:
        return df_i

    nots = (sb.table("market_news")
              .select("id,titulo,resumen,url,fuente,fecha_noticia")
              .in_("id", ids).execute())
    df_n = pd.DataFrame(nots.data) if nots.data else pd.DataFrame()
    if df_n.empty:
        return df_i
    df_n = df_n.rename(columns={"id": "noticia_id"})
    return df_i.merge(df_n, on="noticia_id", how="left")


@_safe_query
def load_raw_news(hours: int = 24, limit: int = 25) -> pd.DataFrame:
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    r = (sb.table("market_news").select("*")
           .gte("fecha_noticia", cutoff)
           .order("relevancia_preliminar", desc=True)
           .order("fecha_noticia", desc=True)
           .limit(limit).execute())
    return pd.DataFrame(r.data)


def load_portfolio_snapshot() -> dict:
    """Resumen del estado actual de la cartera."""
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
    # Calcular retorno: SOLO posiciones con precio_compra válido (>0)
    # ARTY, BITO, EZU, LIT, QQQ, SGML tienen precio_compra=0 (datos faltantes en snapshot)
    # → no se les puede calcular retorno, los excluimos del ranking
    import numpy as np
    df["retorno_pct"] = np.where(
        df["precio_compra"] > 0,
        ((df["precio_actual"] - df["precio_compra"]) / df["precio_compra"] * 100).round(2),
        np.nan,
    )

    # Filtrar solo posiciones con valor significativo (>$100k CLP) y retorno válido
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
        "top_gainers":    df_rankable.nlargest(5, "retorno_pct")[["ticker", "retorno_pct", "valor_clp"]].to_dict("records"),
        "top_losers":     df_rankable.nsmallest(5, "retorno_pct")[["ticker", "retorno_pct", "valor_clp"]].to_dict("records"),
    }


# ── Formato ──────────────────────────────────────────────────
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


# ── HTML Builders ────────────────────────────────────────────
def _section(title: str, content: str) -> str:
    return f"""
    <div style="margin: 28px 0;">
      <h2 style="color:{COLORS['text']}; font-size:18px; margin:0 0 14px 0; border-bottom: 2px solid {COLORS['primary']}; padding-bottom:6px;">
        {title}
      </h2>
      {content}
    </div>
    """


def _build_alerts_html(df: pd.DataFrame) -> str:
    if df.empty:
        return f"<p style='color:{COLORS['text_dim']};'>✅ Sin alertas activas. Cartera en buen estado.</p>"

    # Agrupar por severidad
    counts = df["severidad"].value_counts()
    summary = " · ".join([f"<strong style='color:{SEV_COLOR.get(s,'#888')};'>{int(c)} {s}</strong>"
                          for s, c in counts.items()])

    cards = []
    for _, row in df.head(15).iterrows():
        sev = (row.get("severidad") or "info").lower()
        color = SEV_COLOR.get(sev, "#888")
        cat = (row.get("categoria") or "").upper()
        activo = row.get("activo") or "—"
        cards.append(f"""
        <div style="background:{COLORS['card']}; padding:12px 14px; border-radius:8px; border-left:4px solid {color}; margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:start; flex-wrap:wrap;">
            <strong style="color:{COLORS['text']}; font-size:14px;">{row.get('titulo','')}</strong>
            <span style="background:{color}22; color:{color}; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600;">
              {sev.upper()} · {cat}
            </span>
          </div>
          <div style="color:{COLORS['text_dim']}; font-size:13px; margin-top:6px;">
            <strong>{activo}</strong> · {row.get('mensaje','')}
          </div>
          <div style="color:{COLORS['text_dim']}; font-size:12px; margin-top:6px; font-style:italic;">
            💡 {row.get('sugerencia','')}
          </div>
        </div>""")

    return f"<p style='color:{COLORS['text_dim']}; margin-bottom:14px;'>{summary}</p>" + "\n".join(cards)


def _build_brief_html(brief: str) -> str:
    if not brief:
        return ""
    # Brief en markdown — conversión simple a HTML
    html_brief = (
        brief
        .replace("**", "")  # negrita ya no funcionará 1:1, simplificamos
        .replace("##", "<h3>")
        .replace("\n", "<br>")
    )
    return f"""
    <div style="background:{COLORS['card']}; padding:16px 20px; border-radius:10px; border-left:4px solid {COLORS['primary']}; color:{COLORS['text']}; font-size:14px; line-height:1.6;">
      {html_brief}
    </div>"""


def _build_news_html(df_intel: pd.DataFrame, df_raw: pd.DataFrame) -> str:
    """Render de noticias. Prefiere las analizadas por AI; cae a crudas."""
    if df_intel is None or df_intel.empty:
        if df_raw is None or df_raw.empty:
            return f"<p style='color:{COLORS['text_dim']};'>Sin noticias relevantes en las últimas 24 horas.</p>"
        # Fallback crudas
        items = []
        for _, row in df_raw.head(10).iterrows():
            fecha_str = ""
            try:
                fecha_str = pd.to_datetime(row["fecha_noticia"]).strftime("%d/%m %H:%M")
            except Exception:
                pass
            items.append(f"""
            <div style="border-bottom:1px solid {COLORS['border']}; padding:10px 0;">
              <a href="{row.get('url','#')}" style="color:{COLORS['text']}; text-decoration:none; font-size:14px; font-weight:600;">
                {row.get('titulo','')}
              </a>
              <div style="color:{COLORS['text_dim']}; font-size:12px; margin-top:3px;">
                {row.get('fuente','')} · {fecha_str} · relev {row.get('relevancia_preliminar',0)}
              </div>
              <div style="color:{COLORS['text_dim']}; font-size:13px; margin-top:6px;">
                {(row.get('resumen') or '')[:200]}
              </div>
            </div>""")
        return "\n".join(items)

    # Con análisis AI
    items = []
    for _, row in df_intel.head(12).iterrows():
        tipo = (row.get("tipo") or "neutro").lower()
        color = TIPO_COLOR.get(tipo, "#888")
        rel = row.get("relevancia_pct") or 0
        titulo = row.get("titulo") or "(sin título)"
        url = row.get("url") or "#"
        resumen = row.get("resumen_esp") or ""
        accion = row.get("accion_sugerida") or ""
        fecha_str = ""
        try:
            fecha_str = pd.to_datetime(row["fecha_noticia"]).strftime("%d/%m %H:%M")
        except Exception:
            pass

        tickers = row.get("tickers_afectados") or []
        if isinstance(tickers, str):
            tickers = tickers.strip("{}").split(",")
        tickers_str = ", ".join(t.strip() for t in tickers if t and t.strip())

        items.append(f"""
        <div style="background:{COLORS['card']}; padding:12px 14px; border-radius:8px; border-left:4px solid {color}; margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:start; flex-wrap:wrap;">
            <a href="{url}" style="color:{COLORS['text']}; text-decoration:none; font-size:14px; font-weight:600; flex:1;">
              {titulo}
            </a>
            <span style="background:{color}22; color:{color}; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; margin-left:8px;">
              {tipo.upper()} · {rel}/100
            </span>
          </div>
          <div style="color:{COLORS['text_dim']}; font-size:12px; margin-top:3px;">
            {row.get('fuente','')} · {fecha_str}{(' · ' + tickers_str) if tickers_str else ''}
          </div>
          <div style="color:{COLORS['text_dim']}; font-size:13px; margin-top:8px;">
            {resumen}
          </div>
          {f'<div style="color:{COLORS["yellow"]}; font-size:12px; margin-top:6px; font-weight:500;">🎯 {accion}</div>' if accion else ''}
        </div>""")

    return "\n".join(items)


def _build_portfolio_html(snap: dict) -> str:
    if not snap:
        return f"<p style='color:{COLORS['text_dim']};'>Sin datos de cartera.</p>"

    color_ret = COLORS["green"] if snap["retorno_pct"] >= 0 else COLORS["red"]

    gainers_rows = "".join([
        f"<tr><td style='color:{COLORS['text']};'>{g['ticker']}</td>"
        f"<td style='color:{COLORS['green']}; text-align:right;'>{fmt_pct(g['retorno_pct'])}</td>"
        f"<td style='color:{COLORS['text_dim']}; text-align:right;'>{fmt_clp(g['valor_clp'])}</td></tr>"
        for g in snap["top_gainers"]
    ])
    losers_rows = "".join([
        f"<tr><td style='color:{COLORS['text']};'>{g['ticker']}</td>"
        f"<td style='color:{COLORS['red']}; text-align:right;'>{fmt_pct(g['retorno_pct'])}</td>"
        f"<td style='color:{COLORS['text_dim']}; text-align:right;'>{fmt_clp(g['valor_clp'])}</td></tr>"
        for g in snap["top_losers"]
    ])

    return f"""
    <table style="width:100%; border-collapse:collapse; margin-bottom:18px;">
      <tr>
        <td style="background:{COLORS['card']}; padding:14px; border-radius:8px; text-align:center; width:50%;">
          <div style="color:{COLORS['text_dim']}; font-size:12px;">Patrimonio total</div>
          <div style="color:{COLORS['text']}; font-size:20px; font-weight:700;">{fmt_clp(snap['total_clp'])}</div>
          <div style="color:{color_ret}; font-size:13px;">{fmt_pct(snap['retorno_pct'])} ({fmt_clp(snap['ganancia'])})</div>
        </td>
        <td style="width:8px;"></td>
        <td style="background:{COLORS['card']}; padding:14px; border-radius:8px; text-align:center; width:50%;">
          <div style="color:{COLORS['text_dim']}; font-size:12px;">Posiciones</div>
          <div style="color:{COLORS['text']}; font-size:20px; font-weight:700;">{snap['n_positions']}</div>
          <div style="color:{COLORS['text_dim']}; font-size:13px;">Costo: {fmt_clp(snap['total_costo'])}</div>
        </td>
      </tr>
    </table>

    <table style="width:100%; border-collapse:collapse;">
      <tr>
        <td style="vertical-align:top; width:50%; padding-right:6px;">
          <div style="background:{COLORS['card']}; padding:12px; border-radius:8px;">
            <div style="color:{COLORS['green']}; font-weight:600; font-size:13px; margin-bottom:8px;">📈 Top 5 ganadores</div>
            <table style="width:100%; font-size:13px; border-collapse:collapse;">{gainers_rows}</table>
          </div>
        </td>
        <td style="width:8px;"></td>
        <td style="vertical-align:top; width:50%; padding-left:6px;">
          <div style="background:{COLORS['card']}; padding:12px; border-radius:8px;">
            <div style="color:{COLORS['red']}; font-weight:600; font-size:13px; margin-bottom:8px;">📉 Top 5 perdedores</div>
            <table style="width:100%; font-size:13px; border-collapse:collapse;">{losers_rows}</table>
          </div>
        </td>
      </tr>
    </table>
    """


# ── BUILD PRINCIPAL ──────────────────────────────────────────
def build_daily_report() -> tuple[str, str, str]:
    """
    Construye el email diario.
    Returns: (subject, html_body, text_body)
    """
    print("📊 Cargando datos para el email...")

    df_alerts = load_active_alerts()
    brief     = load_daily_brief()
    df_intel  = load_intel_news(hours=24)
    df_raw    = load_raw_news(hours=24)
    snap      = load_portfolio_snapshot()

    n_alerts = len(df_alerts)
    fecha_es = datetime.now().strftime("%A %d %B %Y")
    meses_es = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
                "May":"mayo","June":"junio","July":"julio","August":"agosto",
                "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
    dias_es  = {"Monday":"lunes","Tuesday":"martes","Wednesday":"miércoles","Thursday":"jueves",
                "Friday":"viernes","Saturday":"sábado","Sunday":"domingo"}
    for k,v in meses_es.items():
        fecha_es = fecha_es.replace(k, v)
    for k,v in dias_es.items():
        fecha_es = fecha_es.replace(k, v)
    fecha_es = fecha_es[0].upper() + fecha_es[1:]  # capitalizar día

    # Subject
    if n_alerts > 0:
        subject = f"🔔 Portfolio Alerts {date.today().strftime('%d/%m')} — {n_alerts} alertas"
    else:
        subject = f"✅ Portfolio Alerts {date.today().strftime('%d/%m')} — sin novedades"

    # Build HTML
    sections = []

    if brief:
        sections.append(_section("🌅 Daily Brief", _build_brief_html(brief)))

    sections.append(_section(f"⚠️ Alertas de cartera ({n_alerts})", _build_alerts_html(df_alerts)))

    sections.append(_section("📰 Noticias que mueven mercados (24h)",
                              _build_news_html(df_intel, df_raw)))

    sections.append(_section("📈 Portafolio status", _build_portfolio_html(snap)))

    sections.append(f"""
        <div style="margin-top:30px; padding-top:18px; border-top:1px solid {COLORS['border']}; color:{COLORS['text_dim']}; font-size:11px; text-align:center;">
          Generado por Financial Dashboard · {date.today().isoformat()}<br>
          <a href="https://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/" style="color:{COLORS['primary']}; text-decoration:none;">
            Ver dashboard completo →
          </a>
        </div>""")

    html = f"""
    <html><head><meta charset="utf-8"></head>
    <body style="background:{COLORS['bg']}; padding:24px 12px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:{COLORS['text']};">
      <div style="max-width:680px; margin:0 auto;">
        <h1 style="color:{COLORS['text']}; font-size:24px; margin:0 0 4px 0;">💼 Portfolio Alerts</h1>
        <p style="color:{COLORS['text_dim']}; margin:0 0 20px 0; font-size:13px;">{fecha_es}</p>
        {''.join(sections)}
      </div>
    </body></html>
    """

    # Text plain fallback
    text = f"""Portfolio Alerts — {fecha_es}

ALERTAS ACTIVAS: {n_alerts}

Patrimonio: {fmt_clp(snap.get('total_clp', 0))} ({fmt_pct(snap.get('retorno_pct', 0))})

Ver dashboard: https://financial-dashboard-vct8zeit23ektc7swnmihr.streamlit.app/
"""

    return subject, html, text


# ── CLI ──────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="No envía email, imprime HTML preview")
    parser.add_argument("--preview", action="store_true",
                        help="Imprime HTML completo y sale (sin enviar)")
    parser.add_argument("--save", type=str, default=None,
                        help="Guarda HTML en archivo para previsualizar en browser")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("📧 DAILY EMAIL — Generando reporte")
    print("=" * 60)

    subject, html, text = build_daily_report()

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"💾 HTML guardado en {args.save}. Ábrelo en el navegador.")
        return

    if args.preview:
        print("\n--- SUBJECT ---")
        print(subject)
        print("\n--- HTML (primer 2000 chars) ---")
        print(html[:2000])
        return

    from intelligence.email_sender import send_email
    ok = send_email(subject, html, text, dry_run=args.dry_run)
    print("✅ OK" if ok else "❌ FALLÓ")


if __name__ == "__main__":
    main()
