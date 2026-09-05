# ============================================================
# CARGA FALABELLA CMR → SUPABASE
#
# Uso:
#   python load_falabella.py --days 35   → busca cartolas nuevas por correo
#   python load_falabella.py --file data/raw/falabella/estado.pdf → manual
#
# AUTOMATIZADO desde 2026-09-04: la cartola real llega de
# EstadodeCuenta@cmr.cl con asunto "Información CMR Mastercard Elite
# Vencimiento DD Mes AAAA" (varía el vencimiento, por eso se matchea solo
# el prefijo "Información CMR"). --days 35 cubre de sobra el ciclo mensual
# aunque el workflow no corra un día puntual.
# ============================================================

import sys, math, argparse
sys.path.insert(0, ".")

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from extractors.falabella_pdf import parse_estado_cuenta
from extractors.gmail_client import (
    get_gmail_service, search_emails, get_email_detail, download_attachments
)
from database.supabase_client import get_client

PDF_DIR = Path("data/raw/falabella")
PDF_DIR.mkdir(parents=True, exist_ok=True)

parser = argparse.ArgumentParser()
parser.add_argument("--file", help="Ruta a UN PDF puntual (carga manual, sin tocar Gmail)")
parser.add_argument("--days", type=int, default=35,
                    help="Buscar cartolas de los últimos N días por correo (default 35)")
args = parser.parse_args()

sb = get_client()
sb.table("falabella_gastos").select("id").limit(1).execute()
print("✅ Supabase conectado")

pdf_paths = []

if args.file:
    p = Path(args.file)
    if not p.exists():
        print(f"❌ No existe: {p}")
        sys.exit(1)
    pdf_paths = [p]
else:
    print(f"📅 Buscando cartolas por correo (últimos {args.days} días)...")
    service = get_gmail_service()
    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
    # "CMR Mastercard" (sin acentos) es más confiable que "Información CMR"
    # para IMAP SUBJECT search — probado 2026-09-04: la palabra con tilde
    # no matchea aunque se normalice, "CMR Mastercard" sí.
    query = f'from:cmr.cl subject:"CMR Mastercard" after:{since}'
    msgs = search_emails(service, query, max_results=10)
    print(f"   {len(msgs)} correo(s) encontrado(s)")
    for m in msgs:
        detail = get_email_detail(service, m["id"])
        try:
            pdfs = download_attachments(service, detail, PDF_DIR)
            pdf_paths.extend(pdfs)
        except Exception as e:
            print(f"   ⚠️ Error descargando adjunto ({type(e).__name__}): {e}")
    if not pdf_paths:
        print("   Nada nuevo. (Si esperabas una cartola, revisar el asunto real en Gmail.)")
        sys.exit(0)

GASTOS_COLS = {"fecha", "descripcion", "monto", "moneda", "categoria", "fuente", "archivo"}


def clean_row(r):
    row = {k: v for k, v in r.items() if k in GASTOS_COLS}
    if hasattr(row.get("fecha"), "isoformat"):
        row["fecha"] = row["fecha"].isoformat()
    for k, v in list(row.items()):
        if isinstance(v, float) and math.isnan(v):
            row[k] = None
    return row


def fetch_all_keys(page_size=1000):
    all_rows, page = [], 0
    while True:
        start = page * page_size
        r = sb.table("falabella_gastos").select("fecha,descripcion,monto,moneda") \
            .range(start, start + page_size - 1).execute()
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows


def make_key(row):
    return (
        row.get("fecha"),
        str(row.get("descripcion") or "").strip().upper(),
        str(round(float(row.get("monto") or 0), 0)),
        row.get("moneda"),
    )


existing_keys = {make_key(r) for r in fetch_all_keys()}
print(f"   falabella_gastos: {len(existing_keys)} filas existentes")

all_dfs = []
for pdf_path in pdf_paths:
    print(f"\n  📄 {pdf_path.name}")
    try:
        df = parse_estado_cuenta(pdf_path)
        if not df.empty:
            all_dfs.append(df)
    except Exception as e:
        print(f"    ⚠️  Error procesando: {e}")

if not all_dfs:
    print("⚠️  No se extrajeron movimientos de ningún PDF.")
    sys.exit(0)

df = pd.concat(all_dfs, ignore_index=True)

registros = []
for r in df.to_dict("records"):
    # Guardamos el valor absoluto (igual que santander_gastos): el signo
    # negativo de "Pago tarjeta cmr" ya se traduce en la categoría Pago TC,
    # que se excluye del análisis de gastos en el dashboard.
    r = dict(r)
    r["monto"] = abs(float(r["monto"]))
    registros.append(clean_row(r))

ok = skip = 0
err_sample = None
for row in registros:
    key = make_key(row)
    if key in existing_keys:
        skip += 1
        continue
    try:
        sb.table("falabella_gastos").insert(row).execute()
        existing_keys.add(key)
        ok += 1
    except Exception as e:
        if err_sample is None:
            err_sample = str(e)

if err_sample and ok == 0:
    print(f"⚠️  Error de inserción (muestra): {err_sample}")

print(f"\n✅ falabella_gastos: {ok} nuevas, {skip} ya existían")
res = sb.table("falabella_gastos").select("id", count="exact").execute()
print(f"   Total en tabla: {res.count} filas")
