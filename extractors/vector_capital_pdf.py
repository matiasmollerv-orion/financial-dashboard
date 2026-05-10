# ============================================================
# VECTOR CAPITAL PDF EXTRACTOR
# Parsea boletas/comprobantes de Vector Capital
# Uso: VALIDACIÓN mensual + extracción de comisiones
# ============================================================

import re
import pdfplumber
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR      = Path(__file__).resolve().parent.parent
RAW_RACIONAL  = BASE_DIR / "data" / "raw" / "racional"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def parse_vector_pdf(pdf_path: Path) -> dict:
    """
    Parsea una boleta de Vector Capital.
    Formato real:
      DOCUMENTO  PRECIO/U    CANTIDAD   DESCUENTO  COMPRA   VENTA
      COMPRA PESO 897,0219   1.114,8               1.000.000
      MONTO TOTAL: $1.000.000
    """
    result = {
        "archivo":    pdf_path.name,
        "fecha":      None,
        "tipo":       None,        # "compra" o "comision"
        "instrumento":None,
        "moneda":     None,
        "precio":     None,
        "cantidad":   None,
        "monto":      None,
        "es_comision":False,
    }

    full_text = ""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    # ── Fecha
    fecha_match = re.search(r'(\d{1,2}\s+de\s+\w+\s+del?\s+\d{4})', full_text, re.IGNORECASE)
    if fecha_match:
        try:
            meses = {
                "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
                "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12
            }
            raw = fecha_match.group(1).lower().replace(" del ", " ").replace(" de ", " ")
            parts = raw.split()
            dia, mes_str, anio = int(parts[0]), parts[1], int(parts[2])
            result["fecha"] = datetime(anio, meses.get(mes_str, 1), dia).date()
        except Exception:
            pass

    # ── Detectar si es comisión
    if "COMISION" in full_text.upper() or "COMISIÓN" in full_text.upper():
        result["es_comision"] = True
        result["tipo"] = "comision"
    else:
        result["tipo"] = "compra"

    # ── Línea principal de transacción
    # Ej: "COMPRA PESO 897,0219 1.114,8 1.000.000"
    trans_match = re.search(
        r'(COMPRA|VENTA|COMISION)\s+(PESO|DOLAR|USD|CLP)?\s*([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)',
        full_text, re.IGNORECASE
    )
    if trans_match:
        operacion, moneda, precio_s, cantidad_s, monto_s = trans_match.groups()
        result["instrumento"] = operacion.upper()
        result["moneda"]      = (moneda or "CLP").upper()
        result["precio"]      = _to_float(precio_s)
        result["cantidad"]    = _to_float(cantidad_s)
        result["monto"]       = _to_float(monto_s)

    # ── Monto total (fallback)
    if not result["monto"]:
        monto_match = re.search(r'MONTO TOTAL\s*:?\s*\$\s*([\d\.,]+)', full_text, re.IGNORECASE)
        if monto_match:
            result["monto"] = _to_float(monto_match.group(1))

    return result


def _to_float(s: str) -> float:
    """Convierte '1.114,8' o '897,0219' o '1.000.000' → float"""
    s = s.strip()
    # Si tiene coma → separador decimal chileno/europeo
    if "," in s and "." in s:
        # Ej: "1.114,8" → 1114.8
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Ej: "897,0219" → 897.0219
        s = s.replace(",", ".")
    else:
        # Ej: "1.000.000" → 1000000
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def process_vector_pdfs(service=None) -> pd.DataFrame:
    """
    Procesa todos los PDFs de Vector Capital guardados en data/raw/racional/.
    Si se pasa service, primero descarga los más recientes desde Gmail.
    """
    if service:
        _download_vector_pdfs(service)

    registros = []
    pdfs = list(RAW_RACIONAL.glob("*.pdf"))
    print(f"📂 Procesando {len(pdfs)} PDFs de Vector Capital...")

    for pdf_path in pdfs:
        print(f"  📄 {pdf_path.name}")
        rec = parse_vector_pdf(pdf_path)
        registros.append(rec)
        tipo  = "💰 COMISIÓN" if rec["es_comision"] else "🛒 COMPRA"
        monto = f"${rec['monto']:,.0f}" if rec["monto"] else "?"
        print(f"     {tipo} | {rec['fecha']} | {monto} {rec['moneda'] or ''}")

    df = pd.DataFrame(registros)
    if not df.empty:
        df = df.sort_values("fecha", na_position="last").reset_index(drop=True)
        PROCESSED_DIR.mkdir(exist_ok=True)
        df.to_csv(PROCESSED_DIR / "vector_capital_comprobantes.csv", index=False)
        print(f"\n💾 Guardado: vector_capital_comprobantes.csv ({len(df)} filas)")

        comisiones = df[df["es_comision"] == True]
        if not comisiones.empty:
            total_com = comisiones["monto"].sum()
            print(f"   Comisiones detectadas: {len(comisiones)} | Total: ${total_com:,.0f}")

    return df


def _download_vector_pdfs(service):
    """Descarga todos los PDFs de Vector Capital desde Gmail."""
    from extractors.gmail_client import search_emails, get_email_detail, download_attachments

    print("📧 Descargando PDFs de Vector Capital...")
    msgs = search_emails(
        service,
        "from:dte_vector_capital@vectorcapital.cl subject:El comprobante de tus últimas transacciones",
        max_results=9999
    )
    for m in msgs:
        detail = get_email_detail(service, m["id"])
        download_attachments(service, detail, RAW_RACIONAL)
