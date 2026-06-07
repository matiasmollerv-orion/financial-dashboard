# ============================================================
# CARGA TRANSACCIONES RACIONAL DESDE PDFs (DriveWealth)
#
# Parsea los correos "Transacciones Racional Stocks DD-MM-YYYY"
# que contienen PDFs de DriveWealth con compras y ventas.
#
# Uso: python load_racional_pdf.py           → histórico completo
#      python load_racional_pdf.py --days 30 → últimos 30 días
#
# Este script complementa load_racional.py (que solo carga los
# emails individuales "Invertiste en X (TICKER)"). Los PDFs de
# DriveWealth contienen TODAS las transacciones (DCA, rebalanceo,
# ventas, etc.) que no se capturan con los emails individuales.
# ============================================================

import sys, re, argparse
from datetime import datetime, timedelta

sys.path.insert(0, ".")

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=None)
parser.add_argument("--dry-run", action="store_true")
args, _ = parser.parse_known_args()

DATE_FILTER = ""
if args.days:
    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
    DATE_FILTER = f" after:{since}"
    print(f"📅 Modo incremental: correos desde {since} ({args.days} días)")
else:
    print("📅 Modo histórico: todos los correos")

from extractors.gmail_client import (
    get_gmail_service, search_emails, get_email_detail, get_email_subject,
)
from database.supabase_client import get_client
import pdfplumber
import tempfile, os

print("=" * 60)
print("📥 CARGA TRANSACCIONES RACIONAL (PDFs DriveWealth)")
print("=" * 60)

service = get_gmail_service()
sb = get_client()


def parse_trade_date(date_str: str) -> str:
    """Convierte M/D/YYYY → YYYY-MM-DD."""
    parts = date_str.split("/")
    if len(parts) == 3:
        m, d, y = parts
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return None


def parse_pdf_transactions(pdf_bytes: bytes) -> list[dict]:
    """Extrae transacciones de un PDF de DriveWealth (Racional Stocks)."""
    transactions = []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp_path = f.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                for line in text.split("\n"):
                    # Dos formatos de PDF DriveWealth:
                    # Nuevo (2025+): TICKER SECURITY C Buy/Sell HH:MM:SS AM QTY PRICE TRADE SETTLE CAP
                    # Viejo (2021-2024): TICKER SECURITY C Buy/Sell QTY PRICE TRADE SETTLE CAP (sin hora)
                    m = re.match(
                        r'^([A-Z][A-Z0-9\.]{0,9})\s+(.+?)\s+C\s+(Buy|Sell)\s+'
                        r'(?:\d{1,2}:\d{2}:\d{2}\s*[AP]M\s+)?'  # hora OPCIONAL
                        r'(-?[\d.]+)\s+'        # quantity
                        r'([\d.]+)\s+'          # price
                        r'(\d{1,2}/\d{1,2}/\d{4})\s+'  # trade date
                        r'(\d{1,2}/\d{1,2}/\d{4})\s+'  # settle date
                        r'(\w+)',               # capacity
                        line
                    )
                    if m:
                        ticker = m.group(1)
                        action = m.group(3)  # Buy or Sell
                        qty = abs(float(m.group(4)))
                        price = float(m.group(5))
                        trade_date = parse_trade_date(m.group(6))

                        if trade_date and qty > 0:
                            transactions.append({
                                "tipo": "compra" if action == "Buy" else "venta",
                                "mercado": "internacional",
                                "empresa": m.group(2).strip(),
                                "ticker": ticker,
                                "acciones": qty,
                                "precio_usd": price,
                                "monto_usd": round(qty * price, 2),
                                "monto_clp": None,
                                "moneda": "USD",
                                "fecha": trade_date,
                                "fuente": "racional_pdf_drivewealth",
                            })
    finally:
        os.unlink(tmp_path)

    return transactions


# ── Buscar correos ──────────────────────────────────────────
query = f"from:racional subject:Transacciones Racional Stocks{DATE_FILTER}"
msgs = search_emails(service, query, max_results=500)
print(f"\n📧 {len(msgs)} correos 'Transacciones Racional Stocks' encontrados")

# ── Cargar claves existentes (para deduplicar) ──────────────
def fetch_existing_keys(page_size=1000):
    all_rows, page = [], 0
    while True:
        start = page * page_size
        r = (sb.table("racional_transacciones")
               .select("fecha,ticker,monto_usd,tipo,acciones")
               .range(start, start + page_size - 1).execute())
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows

existing_rows = fetch_existing_keys()
# Key: (fecha, ticker, tipo, round(acciones, 4))
existing_keys = set()
for r in existing_rows:
    acc = round(float(r.get("acciones") or 0), 4)
    existing_keys.add((r["fecha"], r["ticker"], r.get("tipo", ""), acc))
print(f"   Ya en BD: {len(existing_keys)} transacciones\n")

# ── Procesar cada email ─────────────────────────────────────
total_ok = 0
total_skip = 0
total_err = 0

for i, m in enumerate(msgs):
    detail = get_email_detail(service, m["id"])
    msg_obj = detail.get("_msg")
    subj = get_email_subject(detail)

    # Extract PDF attachment
    pdf_bytes = None
    for part in msg_obj.walk():
        fn = part.get_filename()
        ct = part.get_content_type()
        if (fn and ".pdf" in fn.lower()) or ct == "application/pdf":
            payload = part.get_payload(decode=True)
            if payload and payload[:4] == b"%PDF":
                pdf_bytes = payload
                break
        elif ct == "application/octet-stream":
            payload = part.get_payload(decode=True)
            if payload and payload[:4] == b"%PDF":
                pdf_bytes = payload
                break

    if not pdf_bytes:
        print(f"  ⚠️ Sin PDF: {subj}")
        total_err += 1
        continue

    # Parse transactions from PDF
    transactions = parse_pdf_transactions(pdf_bytes)

    ok = skip = 0
    for tx in transactions:
        # Deduplication key
        key = (tx["fecha"], tx["ticker"], tx["tipo"], round(tx["acciones"], 4))
        if key in existing_keys:
            skip += 1
            continue

        if args.dry_run:
            print(f"  [DRY] {tx['fecha']}  {tx['tipo']:6s}  {tx['ticker']:8s}  "
                  f"qty={tx['acciones']:.6f}  @${tx['precio_usd']:.4f}  = ${tx['monto_usd']:.2f}")
            ok += 1
            existing_keys.add(key)
            continue

        try:
            sb.table("racional_transacciones").insert(tx).execute()
            existing_keys.add(key)
            ok += 1
        except Exception as e:
            print(f"  ❌ Error insertando {tx['ticker']}: {e}")
            total_err += 1

    status = f"✅ {ok} nuevas" if ok else ""
    if skip:
        status += f" · {skip} ya existían"
    if status:
        print(f"  {subj}: {status} ({len(transactions)} en PDF)")

    total_ok += ok
    total_skip += skip

# ── Resumen ─────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"✅ TOTAL nuevas transacciones insertadas: {total_ok}")
print(f"   Ya existían (skip): {total_skip}")
print(f"   Errores: {total_err}")

if not args.dry_run:
    res = sb.table("racional_transacciones").select("id", count="exact").execute()
    print(f"   Total en racional_transacciones: {res.count} filas")
