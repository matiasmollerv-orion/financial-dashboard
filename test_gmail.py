# ============================================================
# TEST: Conexión Gmail y búsqueda de correos financieros
# ============================================================

import sys
sys.path.insert(0, ".")

from extractors.gmail_client import get_gmail_service, search_emails, get_email_detail, get_email_subject, get_email_date

print("🔌 Conectando con Gmail...\n")
service = get_gmail_service()
print("✅ Conexión exitosa!\n")

queries = [
    ("Santander Tarjeta Crédito",
     "from:mensajeria@santander.cl subject:Estado de Cuenta Tarjeta de Crédito"),

    ("Santander Cuenta Corriente",
     "from:mensajeria@santander.cl subject:Cartola Mensual de Cuentas"),

    ("Racional Transacciones Internacionales [FUENTE PRIMARIA]",
     "from:racional@racional.cl subject:Transacciones Racional Stocks"),

    ("Racional Portafolio Nacional [FUENTE PRIMARIA]",
     'from:racional@racional.cl subject:"Portafolio Acciones nacionales"'),

    ("Vector Capital Comprobantes [VALIDACIÓN MENSUAL]",
     "from:dte_vector_capital@vectorcapital.cl subject:El comprobante de tus últimas transacciones"),

    ("Buda Crypto",
     "from:soporte@buda.com subject:Compra programada exitosa"),
]

print("=" * 65)
for nombre, query in queries:
    msgs = search_emails(service, query, max_results=50)
    print(f"\n📧 {nombre}")
    print(f"   Total encontrados: {len(msgs)}")
    for m in msgs[:3]:
        detail = get_email_detail(service, m["id"])
        print(f"   - {get_email_date(detail)[:16]}  |  {get_email_subject(detail)}")
print("\n" + "=" * 65)
print("\n✅ Test completo. Revisa que cada fuente tenga resultados esperados.")
