# ============================================================
# SANTANDER PDF EXTRACTOR
# Parsea cartolas de tarjeta de crédito y cuenta corriente
# ============================================================

import os
import re
import pikepdf
import pdfplumber
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PASSWORD = os.getenv("SANTANDER_PDF_PASSWORD", "")

BASE_DIR       = Path(__file__).resolve().parent.parent
RAW_SANTANDER  = BASE_DIR / "data" / "raw" / "santander"
PROCESSED_DIR  = BASE_DIR / "data" / "processed"


# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------

def unlock_pdf(pdf_path: Path) -> Path:
    """
    Desbloquea un PDF protegido con contraseña.
    Guarda una versión sin contraseña con sufijo _unlocked.
    """
    unlocked_path = pdf_path.with_stem(pdf_path.stem + "_unlocked")
    if unlocked_path.exists():
        return unlocked_path

    with pikepdf.open(str(pdf_path), password=PASSWORD) as pdf:
        pdf.save(str(unlocked_path))

    print(f"  🔓 Desbloqueado: {unlocked_path.name}")
    return unlocked_path


def detect_currency(pdf_path: Path) -> str:
    """
    Detecta si el PDF es en CLP o USD basado en el nombre o contenido.
    """
    name = pdf_path.stem.lower()
    if "dolar" in name or "usd" in name or "dollar" in name:
        return "USD"
    return "CLP"


# ------------------------------------------------------------
# TARJETA DE CRÉDITO
# ------------------------------------------------------------

def parse_tarjeta_credito(pdf_path: Path) -> pd.DataFrame:
    """
    Extrae movimientos del Estado de Cuenta Tarjeta de Crédito.
    Retorna DataFrame con columnas estandarizadas.
    """
    unlocked = unlock_pdf(pdf_path)
    currency = detect_currency(pdf_path)
    rows = []

    with pdfplumber.open(str(unlocked)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                # Patrón: fecha + descripción + monto
                # Ej: "15/03/2024   SUPERMERCADO JUMBO         -45.990"
                match = re.match(
                    r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-]?\d[\d\.,]+)\s*$",
                    line.strip()
                )
                if match:
                    fecha_str, descripcion, monto_str = match.groups()
                    try:
                        fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                        monto = float(monto_str.replace(".", "").replace(",", "."))
                        rows.append({
                            "fecha":       fecha,
                            "descripcion": descripcion.strip(),
                            "monto":       monto,
                            "moneda":      currency,
                            "categoria":  categorize(descripcion),
                            "fuente":      "santander_tarjeta",
                            "archivo":     pdf_path.name,
                        })
                    except ValueError:
                        continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("fecha").reset_index(drop=True)
    print(f"  📄 Tarjeta {currency}: {len(df)} movimientos extraídos")
    return df


# ------------------------------------------------------------
# CUENTA CORRIENTE
# ------------------------------------------------------------

def parse_cuenta_corriente(pdf_path: Path) -> pd.DataFrame:
    """
    Extrae movimientos de la Cartola Mensual de Cuenta Corriente.
    Retorna DataFrame con columnas estandarizadas.
    """
    unlocked = unlock_pdf(pdf_path)
    rows = []

    with pdfplumber.open(str(unlocked)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                # Patrón: fecha + descripción + cargo/abono + saldo
                match = re.match(
                    r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-]?\d[\d\.,]+)\s+([-]?\d[\d\.,]+)\s*$",
                    line.strip()
                )
                if match:
                    fecha_str, descripcion, monto_str, saldo_str = match.groups()
                    try:
                        fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                        monto = float(monto_str.replace(".", "").replace(",", "."))
                        saldo = float(saldo_str.replace(".", "").replace(",", "."))
                        rows.append({
                            "fecha":       fecha,
                            "descripcion": descripcion.strip(),
                            "monto":       monto,
                            "saldo":       saldo,
                            "moneda":      "CLP",
                            "tipo":        "abono" if monto > 0 else "cargo",
                            "fuente":      "santander_cuenta",
                            "archivo":     pdf_path.name,
                        })
                    except ValueError:
                        continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("fecha").reset_index(drop=True)
    print(f"  📄 Cuenta corriente: {len(df)} movimientos extraídos")
    return df


# ------------------------------------------------------------
# CATEGORIZADOR BÁSICO
# ------------------------------------------------------------

CATEGORIAS = {
    "SUPERMERCADO":     "Supermercado",
    "JUMBO":            "Supermercado",
    "LIDER":            "Supermercado",
    "UNIMARC":          "Supermercado",
    "RESTAURANTE":      "Restaurantes",
    "RESTAURANT":       "Restaurantes",
    "SUSHI":            "Restaurantes",
    "UBER EATS":        "Delivery",
    "PEDIDOS YA":       "Delivery",
    "RAPPI":            "Delivery",
    "UBER":             "Transporte",
    "CABIFY":           "Transporte",
    "BENCIN":           "Transporte",
    "COPEC":            "Transporte",
    "NETFLIX":          "Entretenimiento",
    "SPOTIFY":          "Entretenimiento",
    "AMAZON":           "Compras online",
    "FARMACIA":         "Salud",
    "CLINICA":          "Salud",
    "ISAPRE":           "Salud",
    "GIMNASIO":         "Deporte",
    "ARRIENDO":         "Vivienda",
    "DIVIDENDO":        "Vivienda",
    "LUZ":              "Servicios",
    "AGUA":             "Servicios",
    "INTERNET":         "Servicios",
}

def categorize(descripcion: str) -> str:
    desc_upper = descripcion.upper()
    for keyword, categoria in CATEGORIAS.items():
        if keyword in desc_upper:
            return categoria
    return "Otros"


# ------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ------------------------------------------------------------

def process_all_santander() -> dict[str, pd.DataFrame]:
    """
    Procesa todos los PDFs de Santander en data/raw/santander/.
    Retorna dict con DataFrames por tipo.
    """
    results = {
        "tarjeta_clp": pd.DataFrame(),
        "tarjeta_usd": pd.DataFrame(),
        "cuenta_corriente": pd.DataFrame(),
    }

    for pdf_file in RAW_SANTANDER.glob("*.pdf"):
        if "_unlocked" in pdf_file.stem:
            continue

        name = pdf_file.stem.lower()
        print(f"\n📂 Procesando: {pdf_file.name}")

        if "estado" in name or "tarjeta" in name or "credito" in name or "crédito" in name:
            df = parse_tarjeta_credito(pdf_file)
            currency = detect_currency(pdf_file)
            key = "tarjeta_usd" if currency == "USD" else "tarjeta_clp"
            results[key] = pd.concat([results[key], df], ignore_index=True)

        elif "cartola" in name or "cuenta" in name or "corriente" in name:
            df = parse_cuenta_corriente(pdf_file)
            results["cuenta_corriente"] = pd.concat(
                [results["cuenta_corriente"], df], ignore_index=True
            )

    # Guardar CSVs procesados
    PROCESSED_DIR.mkdir(exist_ok=True)
    for key, df in results.items():
        if not df.empty:
            out = PROCESSED_DIR / f"santander_{key}.csv"
            df.to_csv(out, index=False)
            print(f"\n  💾 Guardado: {out.name} ({len(df)} filas)")

    return results


if __name__ == "__main__":
    print("🏦 Procesando PDFs de Santander...\n")
    results = process_all_santander()
    print("\n✅ Listo.")
    for k, df in results.items():
        if not df.empty:
            print(f"\n--- {k} ---")
            print(df.head())
