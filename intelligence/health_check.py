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


# ============================================================
# AUTO-AUDITORÍA — anomalías contra el historial propio
# (patrón scouting-agent: cada corrida se compara con sus ~4
# semanas previas; la cadencia se DERIVA del historial, no se
# hardcodea). Requiere >= MIN_HISTORIA registros para alertar.
# ============================================================
MIN_HISTORIA = 4          # registros mínimos antes de opinar
VENTANA_DIAS = 28         # historial a considerar
CAIDA_PCT = 0.60          # caída >60% vs promedio → anomalía


def _fetch_stats(sb) -> "pd.DataFrame":
    """Historial pipeline_stats (paginado por si crece)."""
    rows, page = [], 0
    cutoff = (date.today() - timedelta(days=VENTANA_DIAS + 7)).isoformat()
    while True:
        r = (sb.table("pipeline_stats").select("*")
             .gte("fecha", cutoff)
             .order("fecha", desc=True)
             .range(page * 1000, page * 1000 + 999).execute())
        rows.extend(r.data)
        if len(r.data) < 1000:
            break
        page += 1
    df = pd.DataFrame(rows)
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.tz_localize(None)
        df["dia"] = df["fecha"].dt.date
    return df


def check_pipeline_anomalies(sb) -> list[dict]:
    """Detecta fallas silenciosas comparando cada script contra su historial.
    Retorna lista de anomalías (dicts con script, tipo, detalle)."""
    try:
        df = _fetch_stats(sb)
    except Exception as e:
        return [{"script": "pipeline_stats", "tipo": "ERROR",
                 "detalle": f"No pude leer pipeline_stats: {str(e)[:100]}"}]
    if df.empty:
        return []  # sin historial aún, nada que opinar

    anomalias = []
    hoy = date.today()

    for script, g in df.groupby("script"):
        g = g.sort_values("fecha")
        n = len(g)

        # 1. Último exit_ok=false (continue-on-error lo esconde en el workflow)
        ultimo = g.iloc[-1]
        if not ultimo["exit_ok"]:
            anomalias.append({
                "script": script, "tipo": "EXIT_FAIL",
                "detalle": f"{script}: última corrida FALLÓ "
                           f"({ultimo['fecha'].strftime('%d/%m %H:%M')}). "
                           f"El workflow lo esconde con continue-on-error.",
            })
            continue  # si falló, lo demás es consecuencia

        if n < MIN_HISTORIA:
            continue  # historial insuficiente — no generar falsos positivos

        con_datos = g[(g["filas_nuevas"].notna()) & (g["filas_nuevas"] > 0)]

        # 2. Cadencia autoderivada: días desde la última inserción vs
        #    3× el intervalo histórico propio (santander≈mensual, buda≈semanal…)
        if len(con_datos) >= MIN_HISTORIA:
            dias_insert = sorted(set(con_datos["dia"]))
            if len(dias_insert) >= 2:
                intervalos = [(b - a).days for a, b in zip(dias_insert, dias_insert[1:])]
                intervalos = [i for i in intervalos if i > 0] or [1]
                cadencia = sum(intervalos) / len(intervalos)
                dias_sin = (hoy - dias_insert[-1]).days
                if dias_sin > max(3 * cadencia, 3):
                    anomalias.append({
                        "script": script, "tipo": "SIN_DATOS",
                        "detalle": f"{script}: 0 filas hace {dias_sin} días "
                                   f"(cadencia histórica: {cadencia:.0f} días). "
                                   f"Corre pero no inserta nada.",
                    })

            # 3. Caída >60% vs promedio 4 semanas (solo con volumen apreciable)
            prom = con_datos["filas_nuevas"].iloc[:-1].mean() if len(con_datos) > 1 else None
            ult_val = con_datos["filas_nuevas"].iloc[-1]
            if prom and prom >= 5 and ult_val < prom * (1 - CAIDA_PCT):
                anomalias.append({
                    "script": script, "tipo": "CAIDA_VOLUMEN",
                    "detalle": f"{script}: última corrida insertó {int(ult_val)} filas "
                               f"vs promedio {prom:.0f} ({(ult_val/prom-1)*100:+.0f}%). "
                               f"Posible carga parcial (¿paginación? ¿fuente caída?).",
                })

        # 4. Tabla estancada: filas_totales sin crecer cuando históricamente crecía
        tot = g[g["filas_totales_tabla"].notna()]
        if len(tot) >= MIN_HISTORIA:
            primera_mitad = tot["filas_totales_tabla"].iloc[: len(tot) // 2]
            crecia = primera_mitad.diff().fillna(0).sum() > 0
            estancada = tot["filas_totales_tabla"].iloc[-MIN_HISTORIA:].nunique() == 1
            dias_estancada = (tot["dia"].iloc[-1] - tot["dia"].iloc[-MIN_HISTORIA]).days
            if crecia and estancada and dias_estancada >= 7:
                anomalias.append({
                    "script": script, "tipo": "TABLA_ESTANCADA",
                    "detalle": f"{script}: {ultimo['tabla_destino']} lleva "
                               f"{dias_estancada}+ días sin crecer "
                               f"({int(tot['filas_totales_tabla'].iloc[-1])} filas) "
                               f"cuando históricamente crecía.",
                })

    return anomalias


def save_pipeline_alerts(sb, anomalias: list[dict]):
    """Publica anomalías como alertas (categoria pipeline_health) para que
    el email diario las muestre en la sección 🩺. Desactiva las previas."""
    try:
        sb.table("portfolio_alerts").update({"activo_alerta": False}) \
          .eq("activo_alerta", True).eq("categoria", "pipeline_health").execute()
    except Exception:
        pass
    for a in anomalias:
        try:
            sb.table("portfolio_alerts").insert({
                "categoria": "pipeline_health",
                "severidad": "alta" if a["tipo"] in ("EXIT_FAIL", "SIN_DATOS") else "media",
                "activo": a["script"],
                "titulo": f"🩺 {a['tipo']}: {a['script']}",
                "mensaje": a["detalle"],
                "metricas": {"tipo": a["tipo"]},
                "sugerencia": "Revisar logs del workflow en GitHub Actions.",
            }).execute()
        except Exception as e:
            print(f"  no pude guardar anomalía {a['script']}: {str(e)[:80]}")


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

    # ── Auto-auditoría: anomalías del pipeline vs historial propio ──
    print("\n🩺 Auto-auditoría del pipeline (pipeline_stats)...")
    anomalias = check_pipeline_anomalies(sb)
    if anomalias:
        for a in anomalias:
            print(f"  🚨 [{a['tipo']}] {a['detalle']}")
    else:
        print("  ✅ Sin anomalías vs historial propio")
    save_pipeline_alerts(sb, anomalias)

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
