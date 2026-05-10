# ============================================================
# CARGA HISTÓRICA SANTANDER → SUPABASE
# Descarga PDFs de Gmail y sube gastos + cuenta corriente
# ============================================================

import sys, warnings, math
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from pathlib import Path
import pandas as pd

from extractors.gmail_client import (
    get_gmail_service, search_emails,
    get_email_detail, get_email_date, get_email_subject,
    download_attachments
)
from extractors.santander_pdf import parse_tarjeta_credito, parse_cuenta_corriente
from database.supabase_client import get_client

# ── Directorios ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PDF_DIR  = BASE_DIR / "data" / "raw" / "santander"
PDF_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("🏦 CARGA HISTÓRICA SANTANDER")
print("=" * 60)

# ── Conexiones ────────────────────────────────────────────
sb = get_client()
sb.table("santander_gastos").select("id").limit(1).execute()
print("✅ Supabase conectado")

service = get_gmail_service()
print("✅ Gmail conectado\n")


# ── PASO 1: Descargar PDFs desde Gmail ───────────────────
print("=" * 60)
print("PASO 1: Descarga de PDFs")
print("=" * 60)

queries = {
    "Tarjeta de Crédito": "from:mensajeria@santander.cl subject:Estado de Cuenta Tarjeta de Crédito",
    "Cuenta Corriente":   "from:mensajeria@santander.cl subject:Cartola Mensual de Cuentas",
}

for label, query in queries.items():
    print(f"\n🔍 {label}")
    messages = search_emails(service, query, max_results=9999)
    print(f"   {len(messages)} correos encontrados")
    n_pdfs = 0
    for m in messages:
        msg_detail = get_email_detail(service, m["id"])
        fecha = get_email_date(msg_detail)
        fecha_tag = ""
        if fecha:
            # Extraer solo YYYYMMDD del string de fecha
            import re
            dm = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", fecha)
            if dm:
                meses = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05",
                         "Jun":"06","Jul":"07","Aug":"08","Sep":"09","Oct":"10",
                         "Nov":"11","Dec":"12"}
                dia, mes_str, anio = dm.groups()
                fecha_tag = f"{anio}{meses.get(mes_str,'00')}{int(dia):02d}_"

        # Renombrar al guardar para identificar origen
        try:
            pdfs = download_attachments(service, msg_detail, PDF_DIR)
        except Exception as e:
            print(f"    ⚠️  Error descargando adjunto ({type(e).__name__}): {e}")
            continue
        # Renombrar con fecha al frente si no lo tienen
        for p in pdfs:
            if fecha_tag and not p.name.startswith("20"):
                nuevo = p.parent / (fecha_tag + p.name)
                try:
                    p.rename(nuevo)
                except Exception:
                    pass
                n_pdfs += 1
            else:
                n_pdfs += 1
    print(f"   {n_pdfs} PDFs descargados en {PDF_DIR}")


# ── PASO 2: Procesar PDFs ─────────────────────────────────
print("\n" + "=" * 60)
print("PASO 2: Procesando PDFs")
print("=" * 60)

all_tarjeta_clp = []
all_tarjeta_usd = []
all_cuenta      = []

pdfs = sorted(PDF_DIR.glob("*.pdf"))
pdfs = [p for p in pdfs if "_unlocked" not in p.stem]
print(f"\n📂 {len(pdfs)} PDFs a procesar")

for pdf_path in pdfs:
    name_lower = pdf_path.stem.lower()
    print(f"\n  📄 {pdf_path.name}")
    try:
        es_cuenta  = any(k in name_lower for k in ["cartola", "cuenta", "corriente"])
        es_dolar   = any(k in name_lower for k in ["dolar", "usd", "dollar"])

        if es_cuenta:
            df = parse_cuenta_corriente(pdf_path)
            if not df.empty:
                all_cuenta.append(df)
        else:
            df = parse_tarjeta_credito(pdf_path)
            if not df.empty:
                if es_dolar:
                    all_tarjeta_usd.append(df)
                else:
                    all_tarjeta_clp.append(df)
    except Exception as e:
        print(f"    ⚠️  Error: {e}")


# ── PASO 3: Subir a Supabase ──────────────────────────────
print("\n" + "=" * 60)
print("PASO 3: Subiendo a Supabase")
print("=" * 60)

USD_CLP = 901.76

def clean_row(r, extra=None):
    row = {k: v for k, v in r.items() if k != "archivo"}
    if hasattr(row.get("fecha"), "isoformat"):
        row["fecha"] = row["fecha"].isoformat()
    for k, v in list(row.items()):
        if isinstance(v, float) and math.isnan(v):
            row[k] = None
    if extra:
        row.update(extra)
    return row

def bulk_insert(tabla, rows):
    ok = 0
    for row in rows:
        try:
            sb.table(tabla).insert(row).execute()
            ok += 1
        except Exception:
            pass
    return ok

# Tarjeta CLP
if all_tarjeta_clp:
    df = pd.concat(all_tarjeta_clp, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_abs = abs(float(r["monto"]))
        registros.append(clean_row(r, {
            "monto_clp": monto_abs,
            "tipo": "cargo" if float(r["monto"]) < 0 else "abono",
            "moneda": "CLP",
        }))
    n = bulk_insert("santander_gastos", registros)
    print(f"  ✅ Tarjeta CLP : {n:>5} filas  ({len(all_tarjeta_clp)} PDFs)")
else:
    print("  ⚠️  Tarjeta CLP : sin datos")

# Tarjeta USD
if all_tarjeta_usd:
    df = pd.concat(all_tarjeta_usd, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_abs = abs(float(r["monto"]))
        registros.append(clean_row(r, {
            "monto_clp": round(monto_abs * USD_CLP, 2),
            "tipo": "cargo" if float(r["monto"]) < 0 else "abono",
            "moneda": "USD",
        }))
    n = bulk_insert("santander_gastos", registros)
    print(f"  ✅ Tarjeta USD : {n:>5} filas  ({len(all_tarjeta_usd)} PDFs)")
else:
    print("  ⚠️  Tarjeta USD : sin datos")

# Cuenta corriente
if all_cuenta:
    df = pd.concat(all_cuenta, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_abs = abs(float(r["monto"]))
        registros.append(clean_row(r, {
            "monto_clp": monto_abs,
            "tipo": "abono" if float(r["monto"]) > 0 else "cargo",
            "moneda": "CLP",
        }))
    n = bulk_insert("santander_cuenta", registros)
    print(f"  ✅ Cuenta CC   : {n:>5} filas  ({len(all_cuenta)} PDFs)")
else:
    print("  ⚠️  Cuenta CC   : sin datos")

# ── Resumen ───────────────────────────────────────────────
print(f"\n{'='*60}")
print("✅ LISTO")
print("="*60)
for tabla in ["santander_gastos", "santander_cuenta"]:
    res = sb.table(tabla).select("id", count="exact").execute()
    print(f"  {tabla}: {res.count} filas")
