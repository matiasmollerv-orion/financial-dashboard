# ============================================================
# CARGA BUDA CRYPTO → SUPABASE
# Uso: python load_buda.py           → histórico
#      python load_buda.py --days 14 → últimos 14 días (incremental)
# ============================================================

import sys, argparse
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
    get_email_detail, get_email_body, get_email_date,
)
from extractors.buda_email import parse_buda
from database.supabase_client import get_client

print("=" * 60)
print("🪙 CARGA BUDA CRYPTO")
print("=" * 60)

service = get_gmail_service()
sb = get_client()

# ── Cargar claves existentes (PAGINADO) ───────────────────
def fetch_all_buda(page_size=1000):
    all_rows, page = [], 0
    while True:
        start = page * page_size
        r = sb.table("buda_crypto").select("fecha,activo,cantidad").range(
            start, start + page_size - 1
        ).execute()
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows


existing_rows = fetch_all_buda()
existing_keys = set(
    (r["fecha"], r["activo"], str(round(float(r.get("cantidad") or 0), 8)))
    for r in existing_rows
)
print(f"\n   Ya en BD: {len(existing_keys)} compras Buda")

# ── Buscar correos ────────────────────────────────────────
query = f"from:soporte@buda.com subject:Compra programada exitosa{DATE_FILTER}"
msgs = search_emails(service, query, max_results=9999 if not args.days else 30)
print(f"📧 {len(msgs)} correos Buda encontrados\n")

# ── Procesar e insertar ───────────────────────────────────
ok = skip = err = 0

for m in msgs:
    detail = get_email_detail(service, m["id"])
    body   = get_email_body(detail)
    date   = get_email_date(detail)
    rec    = parse_buda(body, date)

    if not rec:
        err += 1
        continue

    # Convertir fecha a string ISO
    if hasattr(rec["fecha"], "isoformat"):
        rec["fecha"] = rec["fecha"].isoformat()

    key = (rec["fecha"], rec["activo"], str(round(float(rec.get("cantidad") or 0), 8)))
    if key in existing_keys:
        skip += 1
        continue

    try:
        sb.table("buda_crypto").insert(rec).execute()
        existing_keys.add(key)
        ok += 1
        print(f"  ✅ {rec['fecha']}  {rec['activo']}  {rec['cantidad']:.8f}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        err += 1

print(f"\n{'='*60}")
print(f"  ✅ {ok} nuevas · {skip} ya existían · {err} errores")

res = sb.table("buda_crypto").select("id", count="exact").execute()
print(f"  Total Buda crypto en BD: {res.count} filas")
