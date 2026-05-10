# ============================================================
# CARGA INICIAL A SUPABASE
# Extrae todos los datos desde Gmail/PDFs y los sube a la DB
# ============================================================

import sys, warnings
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from extractors.gmail_client import get_gmail_service
from extractors.racional_email import process_racional_emails
from extractors.buda_email import process_buda_emails
from extractors.vector_capital_pdf import process_vector_pdfs
from database.supabase_client import (
    upsert_racional, upsert_buda,
    upsert_vector_capital, get_client
)

print("="*60)
print("🚀 CARGA INICIAL A SUPABASE")
print("="*60)

# ── Test conexión Supabase
print("\n🔌 Verificando conexión a Supabase...")
try:
    sb = get_client()
    sb.table("racional_transacciones").select("id").limit(1).execute()
    print("✅ Supabase conectado\n")
except Exception as e:
    print(f"❌ Error conexión Supabase: {e}")
    sys.exit(1)

# ── Conectar Gmail
print("🔌 Conectando Gmail...")
service = get_gmail_service()
print("✅ Gmail conectado\n")

# ── 1. RACIONAL
print("="*60)
print("1. RACIONAL (historial completo)")
print("="*60)
df_racional, registros_racional = process_racional_emails(service)

print(f"\n⬆️  Subiendo {len(registros_racional)} transacciones a Supabase...")
# Subir transacciones principales
filas = upsert_racional([{k: v for k, v in r.items() if k != "detalle"} for r in registros_racional])
print(f"✅ Racional transacciones: {filas} filas insertadas")

# Subir detalle portafolio nacional
from database.supabase_client import upsert_racional_nacional_detalle
nacionales_con_detalle = [r for r in registros_racional if r.get("detalle") and r["mercado"] == "nacional"]
detalle_total = 0
for r in nacionales_con_detalle:
    # Buscar el ID insertado
    sb = get_client()
    fecha_str = r["fecha"].isoformat() if hasattr(r["fecha"], "isoformat") else r["fecha"]
    res = sb.table("racional_transacciones").select("id").eq("fecha", fecha_str).eq("mercado", "nacional").eq("monto_clp", r["monto_clp"]).limit(1).execute()
    if res.data:
        trans_id = res.data[0]["id"]
        detalle_rows = [{"fecha": fecha_str, "ticker": d["ticker"], "monto_clp": d["monto_clp"]} for d in r["detalle"]]
        d = upsert_racional_nacional_detalle(detalle_rows, trans_id)
        detalle_total += d
print(f"✅ Detalle portafolio nacional: {detalle_total} filas insertadas")

# ── 2. BUDA
print("\n" + "="*60)
print("2. BUDA CRYPTO (historial completo)")
print("="*60)
df_buda = process_buda_emails(service)

print(f"\n⬆️  Subiendo {len(df_buda)} compras crypto a Supabase...")
buda_records = df_buda.to_dict("records") if not df_buda.empty else []
filas = upsert_buda(buda_records)
print(f"✅ Buda crypto: {filas} filas insertadas")

# ── 3. VECTOR CAPITAL
print("\n" + "="*60)
print("3. VECTOR CAPITAL (descarga + validación)")
print("="*60)
df_vector = process_vector_pdfs(service)

print(f"\n⬆️  Subiendo {len(df_vector)} comprobantes a Supabase...")
vector_records = df_vector.to_dict("records") if not df_vector.empty else []
filas = upsert_vector_capital(vector_records)
print(f"✅ Vector Capital: {filas} filas insertadas")

# ── RESUMEN FINAL
print("\n" + "="*60)
print("✅ CARGA COMPLETA")
print("="*60)

sb = get_client()
for tabla in ["racional_transacciones", "buda_crypto", "vector_capital_comprobantes"]:
    res = sb.table(tabla).select("id", count="exact").execute()
    print(f"  {tabla}: {res.count} filas en Supabase")
