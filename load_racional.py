# ============================================================
# CARGA COMPRAS RACIONAL → SUPABASE
# Uso: python load_racional.py           → histórico
#      python load_racional.py --days 14 → últimos 14 días (incremental)
#
# Maneja DOS tipos de compras:
#   1. Internacional: "Invertiste en Empresa (TICKER)"
#   2. Nacional:      "Invertiste $X en tu Portafolio Acciones nacionales"
# ============================================================

import sys, re, base64, argparse
sys.path.insert(0, ".")

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=None)
args, _ = parser.parse_known_args()

from datetime import datetime, timedelta
DATE_FILTER = ""
if args.days:
    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
    DATE_FILTER = f" after:{since}"
    print(f"📅 Modo incremental: correos desde {since} ({args.days} días)")
else:
    print("📅 Modo histórico: todos los correos")

from extractors.gmail_client import (
    get_gmail_service, search_emails,
    get_email_detail, get_email_date, get_email_subject, get_email_body,
)
from database.supabase_client import get_client

print("=" * 60)
print("📥 CARGA COMPRAS RACIONAL")
print("=" * 60)

service = get_gmail_service()
sb = get_client()


def get_body_text(detail):
    """Wrapper: usa get_email_body de gmail_client (compatible IMAP)."""
    return get_email_body(detail)


def parse_fecha(date_str):
    if not date_str:
        return None
    meses = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
              "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
    m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", date_str)
    if m:
        d, mon, y = m.groups()
        return f"{y}-{meses.get(mon,'01')}-{int(d):02d}"
    return None


def parse_clp(s):
    """'700.000' o '$700.000' → 700000.0"""
    if not s:
        return 0.0
    return float(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s) else 0.0


def parse_usd(s):
    """'1,234.56' → 1234.56"""
    if not s:
        return 0.0
    return float(s.replace(",", ""))


def parse_compra_internacional(subject, body):
    """
    Subject: "Invertiste en Empresa Nombre (TICKER)"
    Body: "Acciones compradas X Precio promedio US$Y Monto comprado US$Z"
    """
    m_subj = re.search(r"Invertiste en\s+(.+?)\s*\(([A-Z0-9\.\-]+)\)", subject, re.IGNORECASE)
    if not m_subj:
        return None
    empresa = m_subj.group(1).strip()
    ticker  = m_subj.group(2).strip().upper()

    text = re.sub(r"\s+", " ", body)

    # Acciones compradas (intentar formato dual y formato simple)
    m_acc = re.search(r"Acciones compradas\s+Acciones vendidas\s+([\d\.]+)", text)
    if not m_acc:
        m_acc = re.search(r"Acciones compradas\s+([\d\.]+)", text)
    acciones = float(m_acc.group(1)) if m_acc else None

    # Precio promedio
    m_precio = re.search(r"Precio promedio\s+US\$\s*([\d\.,]+)", text)
    precio = parse_usd(m_precio.group(1)) if m_precio else None

    # Monto comprado
    m_monto = re.search(r"Monto comprado\s+Monto vendido\s+US\$\s*([\d\.,]+)", text)
    if not m_monto:
        m_monto = re.search(r"Monto comprado\s+US\$\s*([\d\.,]+)", text)
    monto = parse_usd(m_monto.group(1)) if m_monto else None

    if monto is None and acciones and precio:
        monto = round(acciones * precio, 2)

    return {
        "tipo":       "compra",
        "mercado":    "internacional",
        "empresa":    empresa,
        "ticker":     ticker,
        "acciones":   acciones,
        "precio_usd": precio,
        "monto_usd":  monto,
        "monto_clp":  None,
        "moneda":     "USD",
        "fuente":     "racional_invertiste_en",
    }


def parse_compra_nacional(subject, body):
    """
    Subject: "Invertiste $700.000 en tu Portafolio Acciones nacionales"
    """
    m_total = re.search(r"Invertiste\s+\$([\d\.]+)", subject)
    total_clp = parse_clp(m_total.group(1)) if m_total else 0.0

    if total_clp <= 0:
        return None

    return {
        "tipo":       "compra",
        "mercado":    "nacional",
        "empresa":    "Portafolio Acciones Nacionales",
        "ticker":     "PORTFOLIO_CL",
        "acciones":   None,
        "precio_usd": None,
        "monto_usd":  None,
        "monto_clp":  total_clp,
        "moneda":     "CLP",
        "fuente":     "racional_portafolio_nacional",
    }


# ── Buscar correos: dos queries distintas ─────────────────
# 1. Compras internacionales: "Invertiste en TICKER"
# 2. Compras nacionales: "Invertiste $X en tu Portafolio"
# Excluir "Vendiste" para no traerlos (los maneja load_racional_ventas.py)

q_intl = f"from:racional subject:invertiste -subject:portafolio -subject:vendiste{DATE_FILTER}"
q_nac  = f"from:racional subject:invertiste subject:portafolio{DATE_FILTER}"

msgs_intl = search_emails(service, q_intl, max_results=500 if not args.days else 30)
msgs_nac  = search_emails(service, q_nac,  max_results=500 if not args.days else 30)
print(f"\n📧 {len(msgs_intl)} correos compra internacional")
print(f"📧 {len(msgs_nac)} correos compra nacional")

# ── Cargar claves existentes (PAGINADO) ───────────────────
def fetch_all_compras(page_size=1000):
    all_rows, page = [], 0
    while True:
        start = page * page_size
        r = (sb.table("racional_transacciones")
               .select("fecha,ticker,monto_usd,monto_clp,mercado")
               .eq("tipo", "compra")
               .range(start, start + page_size - 1).execute())
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows

existing_rows = fetch_all_compras()
def make_key(row):
    if row.get("mercado") == "nacional":
        return ("nac", row["fecha"], str(round(float(row.get("monto_clp") or 0), 0)))
    return ("intl", row["fecha"], row["ticker"], str(round(float(row.get("monto_usd") or 0), 2)))
existing_keys = set(make_key(r) for r in existing_rows)
print(f"   Ya en BD: {len(existing_keys)} compras\n")

# ── Procesar e insertar ───────────────────────────────────
def process_batch(msgs, parse_fn, label):
    ok = skip = err = 0
    for m in msgs:
        detail  = get_email_detail(service, m["id"])
        subject = get_email_subject(detail)
        fecha   = parse_fecha(get_email_date(detail))
        body    = get_body_text(detail)

        row = parse_fn(subject, body)
        if not row:
            err += 1
            continue
        row["fecha"] = fecha

        key = make_key(row)
        if key in existing_keys:
            skip += 1
            continue

        try:
            sb.table("racional_transacciones").insert(row).execute()
            existing_keys.add(key)
            ok += 1
            monto_str = (f"USD {row['monto_usd']}" if row.get("monto_usd")
                         else f"CLP {row.get('monto_clp', 0):,.0f}")
            print(f"  ✅ {fecha}  {row['ticker']:14s}  {monto_str}")
        except Exception as e:
            print(f"  ❌ Error: {subject}  →  {e}")
            err += 1
    print(f"\n  {label}: ✅ {ok} nuevas · {skip} ya existían · {err} errores")
    return ok, skip, err


total_ok = 0
print("▶ Internacional:")
o, _, _ = process_batch(msgs_intl, parse_compra_internacional, "Internacional")
total_ok += o

print("\n▶ Nacional:")
o, _, _ = process_batch(msgs_nac, parse_compra_nacional, "Nacional")
total_ok += o

# ── Resumen ───────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"✅ TOTAL nuevas compras insertadas: {total_ok}")

res = sb.table("racional_transacciones").select("id", count="exact").eq("tipo", "compra").execute()
print(f"  Total compras en BD: {res.count} filas")
