# ============================================================
# CARGA SANTANDER → SUPABASE
# Uso: python load_santander.py          → histórico completo
#      python load_santander.py --days 14 → solo últimos 14 días
# ============================================================

import sys, warnings, math, argparse
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# ── Argumentos ────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=None,
                    help="Solo buscar correos de los últimos N días (omitir = histórico completo)")
args, _ = parser.parse_known_args()

# Filtro de fecha para Gmail
if args.days:
    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
    DATE_FILTER = f" after:{since}"
    print(f"📅 Modo incremental: correos desde {since} ({args.days} días)")
else:
    DATE_FILTER = ""
    print("📅 Modo histórico: todos los correos")

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
    # Subject real: "Estado de Cuenta Tarjeta de Crédito"
    # IMAP no matchea acentos: usamos solo el prefijo sin tilde.
    "Tarjeta de Crédito": f'from:mensajeria@santander.cl subject:"Estado de Cuenta Tarjeta"{DATE_FILTER}',
    "Cuenta Corriente":   f'from:mensajeria@santander.cl subject:"Cartola Mensual de Cuentas"{DATE_FILTER}',
}

for label, query in queries.items():
    print(f"\n🔍 {label}")
    messages = search_emails(service, query, max_results=9999 if not args.days else 10)
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

# En modo incremental: solo procesar PDFs cuya fecha en el nombre sea reciente
if args.days:
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=args.days)
    def pdf_es_reciente(p):
        # Nombre empieza con YYYYMMDD_
        import re
        m = re.match(r"(\d{8})_", p.name)
        if not m:
            return False  # sin fecha → ignorar en modo incremental
        try:
            return datetime.strptime(m.group(1), "%Y%m%d") >= cutoff
        except ValueError:
            return False
    pdfs_todos = pdfs
    pdfs = [p for p in pdfs if pdf_es_reciente(p)]
    print(f"\n📂 {len(pdfs)} PDFs recientes (de {len(pdfs_todos)} totales) a procesar")
else:
    print(f"\n📂 {len(pdfs)} PDFs a procesar")

for pdf_path in pdfs:
    name_lower = pdf_path.stem.lower()
    print(f"\n  📄 {pdf_path.name}")
    try:
        es_cuenta  = any(k in name_lower for k in ["cartola", "cuenta", "corriente", "_cc"])
        es_dolar   = any(k in name_lower for k in ["dolar", "usd", "dollar"])

        if es_cuenta:
            df = parse_cuenta_corriente(pdf_path)
            if not df.empty:
                all_cuenta.append(df)
        else:
            df = parse_tarjeta_credito(pdf_path)
            if not df.empty:
                # El parser detecta la moneda leyendo el contenido del PDF.
                # Separamos por la columna 'moneda' del DF (no por el nombre del archivo,
                # que muchas veces no contiene "USD"/"dolar").
                if "moneda" in df.columns:
                    df_usd = df[df["moneda"] == "USD"]
                    df_clp = df[df["moneda"] != "USD"]
                    if not df_usd.empty: all_tarjeta_usd.append(df_usd)
                    if not df_clp.empty: all_tarjeta_clp.append(df_clp)
                elif es_dolar:
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

# Columnas válidas por tabla (schema real en Supabase)
GASTOS_COLS  = {"fecha", "descripcion", "monto", "moneda", "categoria", "fuente", "archivo"}
CUENTA_COLS  = {"fecha", "descripcion", "monto", "saldo", "tipo", "moneda", "archivo"}

def clean_row(r, extra=None, allowed_cols=None):
    row = {k: v for k, v in r.items() if k != "archivo"}
    if hasattr(row.get("fecha"), "isoformat"):
        row["fecha"] = row["fecha"].isoformat()
    for k, v in list(row.items()):
        if isinstance(v, float) and math.isnan(v):
            row[k] = None
    if extra:
        row.update(extra)
    # Filtrar solo columnas que existen en la tabla
    if allowed_cols:
        row = {k: v for k, v in row.items() if k in allowed_cols}
    return row

# ── Cargar claves existentes para deduplicar (PAGINADO) ───
print("\n🔍 Cargando claves existentes para deduplicar...")

def fetch_all_keys(tabla, cols="fecha,descripcion,monto,moneda", page_size=1000):
    """Carga TODAS las filas de una tabla con paginación para evitar límite de 1000 filas."""
    all_rows, page = [], 0
    while True:
        start = page * page_size
        r = sb.table(tabla).select(cols).range(start, start + page_size - 1).execute()
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows

def rows_to_keys(rows):
    return set(
        (r["fecha"], (r["descripcion"] or "").strip().upper(),
         str(round(float(r["monto"] or 0), 0)), r["moneda"])
        for r in rows
    )

existing_gastos_keys = rows_to_keys(fetch_all_keys("santander_gastos"))
existing_cuenta_keys = rows_to_keys(fetch_all_keys("santander_cuenta"))
print(f"   santander_gastos: {len(existing_gastos_keys)} filas existentes")
print(f"   santander_cuenta: {len(existing_cuenta_keys)} filas existentes")


def make_key_gastos(row):
    return (
        row.get("fecha"),
        str(row.get("descripcion") or "").strip().upper(),
        str(round(float(row.get("monto") or 0), 0)),
        row.get("moneda"),
    )

def make_key_cuenta(row):
    return (
        row.get("fecha"),
        str(row.get("descripcion") or "").strip().upper(),
        str(round(float(row.get("monto") or 0), 0)),
        row.get("moneda"),
    )


def bulk_insert(tabla, rows, existing_keys, make_key):
    ok = 0
    skip = 0
    err_sample = None
    for row in rows:
        key = make_key(row)
        if key in existing_keys:
            skip += 1
            continue
        try:
            sb.table(tabla).insert(row).execute()
            existing_keys.add(key)
            ok += 1
        except Exception as e:
            if err_sample is None:
                err_sample = str(e)
    if err_sample and ok == 0:
        print(f"    ⚠️  Error de inserción (muestra): {err_sample}")
    return ok, skip

# Tarjeta CLP
if all_tarjeta_clp:
    df = pd.concat(all_tarjeta_clp, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_abs = abs(float(r["monto"]))
        registros.append(clean_row(r, {
            "monto": monto_abs,
            "moneda": "CLP",
        }, allowed_cols=GASTOS_COLS))
    n, s = bulk_insert("santander_gastos", registros, existing_gastos_keys, make_key_gastos)
    print(f"  ✅ Tarjeta CLP : {n:>5} nuevas  {s:>5} ya existían  ({len(all_tarjeta_clp)} PDFs)")
else:
    print("  ⚠️  Tarjeta CLP : sin datos")

# Tarjeta USD (convertida a CLP * 900 para unificar con gastos en pesos)
USD_CLP = 900
if all_tarjeta_usd:
    df = pd.concat(all_tarjeta_usd, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_usd = abs(float(r["monto"]))
        monto_clp = round(monto_usd * USD_CLP)
        registros.append(clean_row(r, {
            "monto": monto_clp,
            "moneda": "USD",   # informativo: indica origen USD aunque el monto ya está en CLP
        }, allowed_cols=GASTOS_COLS))
    n, s = bulk_insert("santander_gastos", registros, existing_gastos_keys, make_key_gastos)
    print(f"  ✅ Tarjeta USD : {n:>5} nuevas  {s:>5} ya existían  (convertido a CLP × {USD_CLP})")
else:
    print("  ⚠️  Tarjeta USD : sin datos")

# Cuenta corriente
if all_cuenta:
    df = pd.concat(all_cuenta, ignore_index=True)
    df = df[df["monto"].notna()].copy()
    registros = []
    for r in df.to_dict("records"):
        monto_abs = abs(float(r["monto"]))
        # Usar tipo del parser (lee CARGO/ABONO de la columna del PDF). Fallback solo si falta.
        tipo_cc = r.get("tipo") or ("abono" if float(r["monto"]) > 0 else "cargo")
        registros.append(clean_row(r, {
            "monto": monto_abs,
            "tipo": tipo_cc,
            "moneda": "CLP",
        }, allowed_cols=CUENTA_COLS))
    n, s = bulk_insert("santander_cuenta", registros, existing_cuenta_keys, make_key_cuenta)
    print(f"  ✅ Cuenta CC   : {n:>5} nuevas  {s:>5} ya existían  ({len(all_cuenta)} PDFs)")
else:
    print("  ⚠️  Cuenta CC   : sin datos")

# ── Resumen ───────────────────────────────────────────────
print(f"\n{'='*60}")
print("✅ LISTO")
print("="*60)
for tabla in ["santander_gastos", "santander_cuenta"]:
    res = sb.table(tabla).select("id", count="exact").execute()
    print(f"  {tabla}: {res.count} filas")
