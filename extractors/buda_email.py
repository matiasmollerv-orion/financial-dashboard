# ============================================================
# BUDA EMAIL EXTRACTOR
# Parsea correos de compra programada de crypto (BTC / ETH)
# ============================================================

import re
import pandas as pd
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

BASE_DIR      = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def parse_date(date_str: str) -> datetime.date:
    try:
        return parsedate_to_datetime(date_str).date()
    except Exception:
        return datetime.today().date()


def parse_buda(body: str, date_str: str):
    """
    Extrae datos de una compra programada de Buda.
    Formato del cuerpo:
      "Se han agregado BTC 0,00008302 a tu billetera de Buda.com."
    """
    # Patrón: moneda + cantidad
    # Acepta: "BTC 0,00008302" o "ETH 0,00123456"
    match = re.search(r'(BTC|ETH)\s+([\d,\.]+)\s+a tu billetera', body)
    if not match:
        # Intento alternativo
        match = re.search(r'agregado\s+(BTC|ETH)\s+([\d,\.]+)', body)
    if not match:
        return None

    moneda   = match.group(1)
    cantidad = float(match.group(2).replace(",", "."))

    return {
        "fecha":    parse_date(date_str),
        "tipo":     "compra_programada",
        "activo":   moneda,
        "cantidad": cantidad,
        "moneda":   moneda,
        "fuente":   "buda_email",
    }


def process_buda_emails(service) -> pd.DataFrame:
    """
    Descarga y parsea todos los correos de Buda.
    Retorna DataFrame con todas las compras crypto.
    """
    from extractors.gmail_client import (
        search_emails, get_email_detail,
        get_email_body, get_email_date
    )

    registros = []
    print("📧 Buscando compras programadas Buda...")

    msgs = search_emails(
        service,
        "from:soporte@buda.com subject:Compra programada exitosa",
        max_results=9999
    )

    for m in msgs:
        detail = get_email_detail(service, m["id"])
        body   = get_email_body(detail)
        date   = get_email_date(detail)
        rec    = parse_buda(body, date)
        if rec:
            registros.append(rec)
            print(f"  ✓ {rec['fecha']} | {rec['activo']} {rec['cantidad']:.8f}")

    df = pd.DataFrame(registros)
    if not df.empty:
        df = df.sort_values("fecha").reset_index(drop=True)
        PROCESSED_DIR.mkdir(exist_ok=True)
        df.to_csv(PROCESSED_DIR / "buda_crypto.csv", index=False)
        print(f"\n💾 Guardado: buda_crypto.csv ({len(df)} filas)")

        # Resumen por activo
        print("\n📊 Resumen acumulado:")
        resumen = df.groupby("activo")["cantidad"].sum()
        for activo, total in resumen.items():
            print(f"  {activo}: {total:.8f}")

    return df
