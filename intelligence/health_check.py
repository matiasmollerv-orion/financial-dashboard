# ============================================================
# HEALTH CHECK — Verifica que el pipeline de datos esté vivo
#
# Corre diariamente. Si detecta datos viejos, envía email de alerta
# vía Gmail SMTP (NO requiere Gmail OAuth, usa App Password).
#
# Esto resuelve el problema de "el workflow dice success pero
# los datos no se actualizan". Te enteras al día siguiente,
# no dentro de 2 semanas cuando notas que no se ven tus compras.
# ============================================================

import sys, os
from datetime import datetime, timezone, timedelta, date
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


# Umbrales de "qué tan vieja puede estar la data"
THRESHOLDS = {
    "cartera_actual":          {"col": "fecha_actualizacion", "max_age_days": 2,  "criticidad": "alta"},
    "santander_gastos":        {"col": "fecha",               "max_age_days": 35, "criticidad": "media"},
    "santander_cuenta":        {"col": "fecha",               "max_age_days": 35, "criticidad": "baja"},
    "racional_transacciones":  {"col": "fecha",               "max_age_days": 14, "criticidad": "alta"},
    "buda_crypto":             {"col": "fecha",               "max_age_days": 14, "criticidad": "baja"},
}


def check_table_freshness(sb, table: str, col: str, max_age_days: int) -> dict:
    """Retorna dict con status de freshness de una tabla."""
    try:
        r = sb.table(table).select(col).order(col, desc=True).limit(1).execute()
        if not r.data:
            return {"table": table, "status": "EMPTY", "last_date": None, "age_days": None}
        last_val = r.data[0][col]
        last_dt = pd.to_datetime(last_val).date()
        today = date.today()
        age = (today - last_dt).days
        status = "OK" if age <= max_age_days else "STALE"
        return {
            "table": table,
            "status": status,
            "last_date": last_dt.isoformat(),
            "age_days": age,
            "threshold": max_age_days,
        }
    except Exception as e:
        return {"table": table, "status": "ERROR", "error": str(e)[:200]}


def build_alert_html(checks: list[dict]) -> str:
    """Construye HTML para email de alerta."""
    rows = ""
    for c in checks:
        status = c.get("status", "?")
        color = {"OK": "#2ecc71", "STALE": "#e74c3c", "EMPTY": "#e74c3c", "ERROR": "#8b0000"}.get(status, "#888")
        last = c.get("last_date") or "—"
        age = c.get("age_days")
        age_str = f"{age}d" if age is not None else "—"
        threshold = c.get("threshold", "?")
        rows += f"""
        <tr>
          <td style="padding:8px; border-bottom:1px solid #2d3250;"><strong>{c['table']}</strong></td>
          <td style="padding:8px; border-bottom:1px solid #2d3250; color:{color}; font-weight:bold;">{status}</td>
          <td style="padding:8px; border-bottom:1px solid #2d3250;">{last}</td>
          <td style="padding:8px; border-bottom:1px solid #2d3250;">{age_str} / max {threshold}d</td>
        </tr>"""

    return f"""
<html><body style="background:#0e1117; font-family:Arial,sans-serif; padding:20px; color:#ccd6f6;">
  <div style="max-width:600px; margin:0 auto;">
    <h1 style="color:#e74c3c;">🚨 Financial Dashboard — Health Alert</h1>
    <p>Una o más tablas tienen data más vieja de lo esperado. Esto significa que <strong>el flujo diario no está cargando datos correctamente</strong>.</p>

    <p><strong>Causa más común</strong>: token Gmail expirado. Para regenerarlo:</p>
    <ol>
      <li>En tu Mac, abre terminal y corre: <code style="background:#1e2130; padding:4px 8px; border-radius:4px;">cd ~/Documents/Claude/FinancialDashboard && python load_santander.py --days 1</code></li>
      <li>Se abrirá el navegador, autentica con tu Gmail</li>
      <li>Después convierte el nuevo token a base64 y actualízalo en GitHub Secrets como GMAIL_TOKEN_PICKLE: <code>base64 -i config/token.pickle | pbcopy</code></li>
      <li>Anda a https://github.com/matiasmollerv-orion/financial-dashboard/settings/secrets/actions y pega como GMAIL_TOKEN_PICKLE</li>
      <li>Re-ejecuta manualmente el workflow: <code>gh workflow run daily-update.yml</code></li>
    </ol>

    <h2>Estado de tablas ({date.today().isoformat()})</h2>
    <table style="width:100%; border-collapse:collapse; background:#1e2130; border-radius:8px; overflow:hidden;">
      <tr style="background:#2d3250;">
        <th style="padding:8px; text-align:left;">Tabla</th>
        <th style="padding:8px; text-align:left;">Estado</th>
        <th style="padding:8px; text-align:left;">Última fecha</th>
        <th style="padding:8px; text-align:left;">Antigüedad</th>
      </tr>
      {rows}
    </table>

    <p style="margin-top:20px; color:#8892b0; font-size:12px;">
      Esta alerta solo se envía cuando hay problema real. Si todo está OK no recibirás nada.
    </p>
  </div>
</body></html>
"""


def send_alert_email(subject: str, html_body: str) -> bool:
    """Envía email via Gmail SMTP. NO depende del token OAuth."""
    try:
        from intelligence.email_sender import send_email
        return send_email(subject, html_body, "Health check alert", dry_run=False)
    except Exception as e:
        print(f"❌ No se pudo enviar email: {e}")
        return False


def main():
    print("=" * 60)
    print("🏥 HEALTH CHECK — Financial Dashboard Pipeline")
    print("=" * 60)

    sb = get_client()
    checks = []
    has_alert = False

    for table, config in THRESHOLDS.items():
        result = check_table_freshness(sb, table, config["col"], config["max_age_days"])
        result["criticidad"] = config["criticidad"]
        checks.append(result)

        status = result["status"]
        age = result.get("age_days", "?")
        last = result.get("last_date", "?")
        icon = {"OK": "✅", "STALE": "🚨", "EMPTY": "⚠️", "ERROR": "❌"}.get(status, "?")
        print(f"  {icon} {table:30s} | {status:6s} | last={last} | age={age}d")

        if status in ("STALE", "EMPTY", "ERROR") and config["criticidad"] in ("alta", "media"):
            has_alert = True

    if has_alert:
        print("\n🚨 Hay tablas stale. Enviando email de alerta...")
        n_stale = sum(1 for c in checks if c["status"] in ("STALE", "EMPTY", "ERROR"))
        subject = f"🚨 Financial Dashboard — {n_stale} tablas con data vieja"
        html = build_alert_html(checks)
        if send_alert_email(subject, html):
            print("✅ Email de alerta enviado")
        else:
            print("❌ No se pudo enviar alerta (revisar credenciales SMTP)")
        sys.exit(1)  # Fallar el workflow para que GitHub lo marque rojo
    else:
        print("\n✅ Todas las tablas frescas. Sin alertas.")


if __name__ == "__main__":
    main()
