# ============================================================
# CARGA VENTAS RACIONAL → SUPABASE
# Parsea correos "Vendiste X (TICKER)" de racional
# ============================================================

import sys, re, base64
sys.path.insert(0, ".")

from extractors.gmail_client import (
    get_gmail_service, search_emails,
    get_email_detail, get_email_date, get_email_subject,
)
from database.supabase_client import get_client

print("=" * 60)
print("📤 CARGA VENTAS RACIONAL")
print("=" * 60)

service = get_gmail_service()
sb = get_client()

def get_body_text(detail):
    """Extrae texto plano del email."""
    def recurse(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
        if mime == "text/html" and data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", html)
        for p in part.get("parts", []):
            r = recurse(p)
            if r:
                return r
        return ""
    return recurse(detail.get("payload", {}))


def parse_fecha(date_str):
    """Convierte fecha del email a YYYY-MM-DD."""
    import re
    from datetime import datetime
    if not date_str:
        return None
    meses = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
              "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
    m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", date_str)
    if m:
        d, mon, y = m.groups()
        return f"{y}-{meses.get(mon,'01')}-{int(d):02d}"
    return None


def parse_venta_email(subject, body):
    """
    Extrae datos de venta del correo.
    Subject: "Vendiste Empresa Nombre (TICKER)"
    Body contiene: "Acciones vendidas X Precio promedio US$Y Monto vendido US$Z"
    """
    # Ticker y empresa desde subject
    m_subj = re.match(r"Vendiste\s+(.+?)\s*\(([A-Z0-9\.\-]+)\)", subject, re.IGNORECASE)
    if not m_subj:
        return None
    empresa = m_subj.group(1).strip()
    ticker  = m_subj.group(2).strip().upper()

    # Limpiar cuerpo (comprimir espacios)
    text = re.sub(r"\s+", " ", body)

    # Acciones vendidas
    m_acc = re.search(r"Acciones vendidas\s+([\d\.]+)", text)
    acciones = float(m_acc.group(1)) if m_acc else None

    # Precio promedio
    m_precio = re.search(r"Precio promedio\s+US\$\s*([\d\.,]+)", text)
    precio = float(m_precio.group(1).replace(",", "")) if m_precio else None

    # Monto vendido
    m_monto = re.search(r"Monto vendido\s+US\$\s*([\d\.,]+)", text)
    monto = float(m_monto.group(1).replace(",", "")) if m_monto else None

    # Si no tenemos monto pero sí acciones y precio, calcular
    if monto is None and acciones and precio:
        monto = round(acciones * precio, 2)

    return {
        "tipo":    "venta",
        "mercado": "internacional",
        "empresa": empresa,
        "ticker":  ticker,
        "acciones": acciones,
        "precio_usd": precio,
        "monto_usd": monto,
        "monto_clp": None,
        "moneda":  "USD",
        "fuente":  "racional_vendiste",
    }


# ── Buscar todos los correos ──────────────────────────────
msgs = search_emails(service, "from:racional subject:vendiste", max_results=500)
print(f"\n📧 {len(msgs)} correos 'Vendiste' encontrados")

# ── Ver ventas ya cargadas para no duplicar ───────────────
existing = sb.table("racional_transacciones").select("fecha,ticker,monto_usd").eq("tipo","venta").execute()
existing_keys = set(
    (r["fecha"], r["ticker"], str(round(float(r["monto_usd"] or 0), 2)))
    for r in existing.data
)
print(f"   Ya en BD: {len(existing_keys)} ventas")

# ── Parsear e insertar ────────────────────────────────────
ok = 0
skip = 0
err = 0

for m in msgs:
    detail  = get_email_detail(service, m["id"])
    subject = get_email_subject(detail)
    fecha   = parse_fecha(get_email_date(detail))
    body    = get_body_text(detail)

    row = parse_venta_email(subject, body)
    if not row:
        print(f"  ⚠️  No parseado: {subject}")
        err += 1
        continue

    row["fecha"] = fecha

    # Deduplicar
    key = (fecha, row["ticker"], str(round(row["monto_usd"] or 0, 2)))
    if key in existing_keys:
        skip += 1
        continue

    try:
        sb.table("racional_transacciones").insert(row).execute()
        existing_keys.add(key)
        ok += 1
        print(f"  ✅ {fecha}  {row['ticker']:6s}  {row['acciones']} acciones @ ${row['precio_usd']}  = ${row['monto_usd']}")
    except Exception as e:
        print(f"  ❌ Error insertando {subject}: {e}")
        err += 1

print(f"\n{'='*60}")
print(f"  Insertadas: {ok}")
print(f"  Ya existían: {skip}")
print(f"  Errores: {err}")

# ── Resumen en BD ─────────────────────────────────────────
res = sb.table("racional_transacciones").select("tipo", count="exact").execute()
print(f"\n  Total en racional_transacciones: {res.count} filas")
ventas = sb.table("racional_transacciones").select("tipo").eq("tipo","venta").execute()
print(f"  De las cuales ventas: {len(ventas.data)}")

# Total monto vendido
v_data = sb.table("racional_transacciones").select("monto_usd,fecha").eq("tipo","venta").execute()
import pandas as pd
df_v = pd.DataFrame(v_data.data)
if not df_v.empty:
    df_v["monto_usd"] = pd.to_numeric(df_v["monto_usd"], errors="coerce")
    print(f"  Total USD vendido: ${df_v['monto_usd'].sum():,.2f}")
    print(f"  Período: {df_v['fecha'].min()} → {df_v['fecha'].max()}")
