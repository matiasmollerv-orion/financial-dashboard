# ============================================================
# TEST: Ver contenido real de cada correo
# Para construir los parsers correctamente
# ============================================================

import sys
sys.path.insert(0, ".")

from extractors.gmail_client import (
    get_gmail_service, search_emails, get_email_detail,
    get_email_body, get_email_subject, get_email_date,
    download_attachments
)
from pathlib import Path

print("🔌 Conectando con Gmail...\n")
service = get_gmail_service()

# ── 1. RACIONAL INTERNACIONAL ─────────────────────────────
print("\n" + "="*65)
print("1. RACIONAL - INVERTISTE EN [EMPRESA] (Internacional)")
print("="*65)
msgs = search_emails(service, 'from:racional@racional.cl subject:"Invertiste en"', max_results=1)
if msgs:
    detail = get_email_detail(service, msgs[0]["id"])
    print(f"Asunto : {get_email_subject(detail)}")
    print(f"Fecha  : {get_email_date(detail)}")
    print(f"\nCUERPO:\n{'-'*40}")
    print(get_email_body(detail)[:2000])

# ── 2. RACIONAL PORTAFOLIO NACIONAL ───────────────────────
print("\n" + "="*65)
print("2. RACIONAL - PORTAFOLIO ACCIONES NACIONALES")
print("="*65)
msgs = search_emails(service, 'from:racional@racional.cl subject:"Portafolio Acciones nacionales"', max_results=1)
if msgs:
    detail = get_email_detail(service, msgs[0]["id"])
    print(f"Asunto : {get_email_subject(detail)}")
    print(f"Fecha  : {get_email_date(detail)}")
    print(f"\nCUERPO:\n{'-'*40}")
    print(get_email_body(detail)[:2000])

# ── 3. BUDA CRYPTO ────────────────────────────────────────
print("\n" + "="*65)
print("3. BUDA - COMPRA PROGRAMADA EXITOSA")
print("="*65)
msgs = search_emails(service, "from:soporte@buda.com subject:Compra programada exitosa", max_results=1)
if msgs:
    detail = get_email_detail(service, msgs[0]["id"])
    print(f"Asunto : {get_email_subject(detail)}")
    print(f"Fecha  : {get_email_date(detail)}")
    print(f"\nCUERPO:\n{'-'*40}")
    print(get_email_body(detail)[:2000])

# ── 4. VECTOR CAPITAL - descargar 1 PDF de muestra ────────
print("\n" + "="*65)
print("4. VECTOR CAPITAL - COMPROBANTE (descargando 1 PDF de muestra)")
print("="*65)
msgs = search_emails(service, "from:dte_vector_capital@vectorcapital.cl subject:El comprobante de tus últimas transacciones", max_results=1)
if msgs:
    detail = get_email_detail(service, msgs[0]["id"])
    print(f"Asunto : {get_email_subject(detail)}")
    print(f"Fecha  : {get_email_date(detail)}")
    dest = Path("data/raw/racional")
    saved = download_attachments(service, detail, dest)
    print(f"PDFs descargados: {[p.name for p in saved]}")

print("\n✅ Listo. Revisa los cuerpos para construir los parsers.")
