# ============================================================
# TEST: Probar los 3 extractores con datos reales
# ============================================================
import sys, warnings
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from extractors.gmail_client import get_gmail_service
from extractors.racional_email import process_racional_emails
from extractors.buda_email import process_buda_emails
from extractors.vector_capital_pdf import process_vector_pdfs

print("🔌 Conectando con Gmail...\n")
service = get_gmail_service()

print("\n" + "="*60)
print("1. RACIONAL (Internacionales + Nacional)")
print("="*60)
df_racional, registros = process_racional_emails(service)

print("\n" + "="*60)
print("2. BUDA CRYPTO")
print("="*60)
df_buda = process_buda_emails(service)

print("\n" + "="*60)
print("3. VECTOR CAPITAL PDFs (validación)")
print("="*60)
df_vector = process_vector_pdfs(service)

print("\n\n✅ RESUMEN FINAL")
print("="*60)
print(f"  Racional transacciones : {len(df_racional)} registros")
print(f"  Buda crypto            : {len(df_buda)} registros")
print(f"  Vector Capital PDFs    : {len(df_vector)} registros")
