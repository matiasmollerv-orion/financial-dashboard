# ============================================================
# RACIONAL EMAIL EXTRACTOR
# Parsea correos de inversiones internacionales y portafolio nacional
# ============================================================

import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

BASE_DIR      = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


# ── UTILS ────────────────────────────────────────────────────

def clean_clp(value: str) -> float:
    """Convierte '$83.908' o '83.908' → 83908.0"""
    return float(value.replace("$", "").replace(".", "").replace(",", ".").strip())

def clean_usd(value: str) -> float:
    """Convierte 'US$600.34' o '600.34' → 600.34"""
    return float(value.replace("US$", "").replace("$", "").replace(",", "").strip())

def parse_date(date_str: str) -> datetime.date:
    try:
        return parsedate_to_datetime(date_str).date()
    except Exception:
        return datetime.today().date()


# ── INTERNACIONAL: "Invertiste en Meta Platforms (META)" ─────

def parse_internacional(body: str, subject: str, date_str: str) -> dict:
    """
    Extrae datos de una compra de acción internacional.
    Fuente: correo "Invertiste en [Empresa] (TICKER)" de racional@racional.cl
    """
    # Ticker y empresa desde el asunto
    ticker_match = re.search(r'\(([A-Z]+)\)\s*$', subject)
    ticker = ticker_match.group(1) if ticker_match else "UNKNOWN"

    company_match = re.search(r'Invertiste en (.+?)\s*\(', subject)
    empresa = company_match.group(1).strip() if company_match else "UNKNOWN"

    # Acciones compradas: "Acciones compradas Acciones vendidas 0.6662891"
    shares_match = re.search(r'Acciones compradas\s+Acciones vendidas\s+([\d\.]+)', body)
    if not shares_match:
        shares_match = re.search(r'compradas\D+([\d]+\.[\d]+)', body)
    acciones = float(shares_match.group(1)) if shares_match else 0.0

    # Precio promedio: "Precio promedio US$600.34"
    precio_match = re.search(r'Precio promedio\s+US\$([\d\.,]+)', body)
    precio_usd = clean_usd(precio_match.group(1)) if precio_match else 0.0

    # Monto comprado: "Monto comprado Monto vendido US$400"
    monto_match = re.search(r'Monto comprado\s+Monto vendido\s+US\$([\d\.,]+)', body)
    if not monto_match:
        monto_match = re.search(r'Monto comprado\s+US\$([\d\.,]+)', body)
    monto_usd = clean_usd(monto_match.group(1)) if monto_match else 0.0

    return {
        "fecha":      parse_date(date_str),
        "tipo":       "compra",
        "mercado":    "internacional",
        "empresa":    empresa,
        "ticker":     ticker,
        "acciones":   acciones,
        "precio_usd": precio_usd,
        "monto_usd":  monto_usd,
        "monto_clp":  None,
        "moneda":     "USD",
        "fuente":     "racional_invertiste_en",
    }


# ── NACIONAL: "Invertiste $X en tu Portafolio Acciones nacionales" ──

def parse_nacional(body: str, subject: str, date_str: str) -> dict:
    """
    Extrae datos de una inversión en el portafolio de acciones nacionales.
    Fuente: correo "Invertiste $X en tu Portafolio..." de racional@racional.cl
    """
    # Total desde el asunto: "Invertiste $700.000 en tu Portafolio..."
    total_match = re.search(r'Invertiste\s+\$([\d\.]+)', subject)
    total_clp = clean_clp(total_match.group(1)) if total_match else 0.0

    # Detalle por acción desde el HTML del cuerpo
    # Patrón: <td>CHILE</td><td>$83.908</td>
    soup = BeautifulSoup(body, "html.parser")
    filas = soup.find_all("tr")

    detalle = []
    for fila in filas:
        celdas = fila.find_all("td")
        if len(celdas) >= 2:
            nombre = celdas[0].get_text(strip=True)
            valor_raw = celdas[1].get_text(strip=True)
            # Filtrar solo filas con nombre en mayúsculas y valor con $
            if nombre.isupper() and "$" in valor_raw and len(nombre) >= 2:
                try:
                    monto = clean_clp(valor_raw)
                    detalle.append({"ticker": nombre, "monto_clp": monto})
                except ValueError:
                    continue

    return {
        "fecha":      parse_date(date_str),
        "tipo":       "compra",
        "mercado":    "nacional",
        "empresa":    "Portafolio Acciones Nacionales",
        "ticker":     "PORTFOLIO_CL",
        "acciones":   None,
        "precio_usd": None,
        "monto_usd":  None,
        "monto_clp":  total_clp,
        "moneda":     "CLP",
        "fuente":     "racional_portafolio_nacional",
        "detalle":    detalle,          # breakdown por acción
    }


# ── PROCESADOR PRINCIPAL ─────────────────────────────────────

def process_racional_emails(service) -> pd.DataFrame:
    """
    Descarga y parsea todos los correos de Racional.
    Retorna DataFrame con todas las transacciones sin duplicados.
    """
    from extractors.gmail_client import (
        search_emails, get_email_detail,
        get_email_body, get_email_subject, get_email_date
    )

    registros = []

    # ── Internacionales (sin límite → trae TODO el historial)
    print("📧 Buscando inversiones internacionales (historial completo)...")
    msgs = search_emails(service, 'from:racional@racional.cl subject:"Invertiste en"', max_results=9999)
    # Excluir los de portafolio nacional que también contienen "Invertiste en"
    for m in msgs:
        detail  = get_email_detail(service, m["id"])
        subject = get_email_subject(detail)
        if "Portafolio" in subject or "portafolio" in subject:
            continue                        # es nacional, se procesa aparte
        body    = get_email_body(detail)
        date    = get_email_date(detail)
        rec     = parse_internacional(body, subject, date)
        registros.append(rec)
        print(f"  ✓ {rec['fecha']} | {rec['ticker']} | US${rec['monto_usd']}")

    # ── Nacionales (sin límite → trae TODO el historial)
    print("\n📧 Buscando inversiones portafolio nacional (historial completo)...")
    msgs = search_emails(service, 'from:racional@racional.cl subject:"Portafolio Acciones nacionales"', max_results=9999)
    for m in msgs:
        detail  = get_email_detail(service, m["id"])
        subject = get_email_subject(detail)
        body    = get_email_body(detail)
        date    = get_email_date(detail)
        rec     = parse_nacional(body, subject, date)
        registros.append(rec)
        print(f"  ✓ {rec['fecha']} | Nacional | ${rec['monto_clp']:,.0f} CLP | {len(rec.get('detalle', []))} acciones")

    # Armar DataFrame principal (sin columna detalle)
    df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "detalle"}
        for r in registros
    ])

    if not df.empty:
        df = df.sort_values("fecha").reset_index(drop=True)
        PROCESSED_DIR.mkdir(exist_ok=True)
        df.to_csv(PROCESSED_DIR / "racional_transacciones.csv", index=False)
        print(f"\n💾 Guardado: racional_transacciones.csv ({len(df)} filas)")

    return df, registros
