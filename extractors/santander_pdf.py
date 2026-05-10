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
    Detecta si el PDF es en CLP o USD.
    Primero revisa el nombre del archivo; si no hay pista, lee el contenido.
    """
    name = pdf_path.stem.lower()
    if "dolar" in name or "usd" in name or "dollar" in name:
        return "USD"

    # Buscar indicadores en el contenido del PDF (usa la versión desbloqueada si existe)
    unlocked = pdf_path.with_stem(pdf_path.stem + "_unlocked")
    check_path = unlocked if unlocked.exists() else pdf_path
    try:
        with pdfplumber.open(str(check_path)) as pdf:
            for page in pdf.pages[:2]:          # Solo primeras 2 páginas
                text = (page.extract_text() or "").upper()
                if "DÓLAR" in text or "DOLARES" in text or "USD" in text or "US$" in text:
                    return "USD"
    except Exception:
        pass
    return "CLP"


# ------------------------------------------------------------
# TARJETA DE CRÉDITO
# ------------------------------------------------------------

def _parse_monto(s: str) -> float:
    """Parsea monto en formato chileno (punto miles, coma decimal) o USD (coma decimal)."""
    s = s.strip().replace("$", "").strip()
    # Si tiene coma y luego exactamente 2 dígitos al final → decimal americano/europeo
    if re.search(r",\d{2}$", s) and "." not in s:
        return float(s.replace(",", "."))
    # Formato chileno: punto como miles, coma como decimal (o solo puntos como miles)
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _clean_desc(raw: str) -> str:
    """Limpia la descripción eliminando info de cuotas, tasas y espacios extras."""
    d = raw.strip()
    # Eliminar info de cuotas: "2,02 %" / "0,00 %" / "N/CUOTAS" / "03/03" etc.
    d = re.sub(r"\s+\d+[,\.]\d+\s*%.*", "", d)
    d = re.sub(r"\s+N/CUOTAS.*", "", d, flags=re.IGNORECASE)
    # Eliminar "PREC" o "PRECIO" y todo lo que sigue
    d = re.sub(r"\s+PREC\b.*", "", d, flags=re.IGNORECASE)
    return d.strip()


def parse_tarjeta_credito(pdf_path: Path) -> pd.DataFrame:
    """
    Extrae movimientos del Estado de Cuenta Tarjeta de Crédito.
    Soporta el formato CLP (monto precedido por $) y USD (último número de la línea).
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
                line = line.strip()
                if not line:
                    continue

                fecha_str = descripcion = monto_str = None

                if currency == "CLP":
                    # Patrón CLP: [CIUDAD ]DD/MM/YYYY DESCRIPCIÓN … $ MONTO_FINAL
                    # Con .+ greedy captura todo hasta el ÚLTIMO $ (así maneja cuotas)
                    m = re.search(
                        r"(\d{2}/\d{2}/\d{4})\s+(.+)\$\s*([-]?\d[\d\.,]*)\s*$",
                        line
                    )
                    if m:
                        fecha_str    = m.group(1)
                        descripcion  = _clean_desc(m.group(2))
                        monto_str    = m.group(3)

                else:  # USD
                    # Patrón USD: DD/MM/YYYY DESCRIPCIÓN CIUDAD PAÍS MONTO_ORIG MONTO_USD
                    # El último número es el monto en USD
                    m = re.match(
                        r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-]?\d[\d\.,]+)\s*$",
                        line
                    )
                    if m:
                        fecha_str   = m.group(1)
                        descripcion = m.group(2).strip()
                        monto_str   = m.group(3)

                if not fecha_str:
                    continue

                try:
                    fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                    monto = _parse_monto(monto_str)
                    if monto == 0 or not descripcion:
                        continue
                    rows.append({
                        "fecha":       fecha,
                        "descripcion": descripcion,
                        "monto":       monto,
                        "moneda":      currency,
                        "categoria":   categorize(descripcion),
                        "fuente":      "santander_tarjeta",
                        "archivo":     pdf_path.name,
                    })
                except (ValueError, ZeroDivisionError):
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
    # ── Supermercado ───────────────────────────────────────
    "SUPERMERCADO":     "Supermercado",
    "JUMBO":            "Supermercado",
    "LIDER":            "Supermercado",
    "UNIMARC":          "Supermercado",
    "SANTA ISABEL":     "Supermercado",
    "TOTTUS":           "Supermercado",
    "EKONO":            "Supermercado",
    "WALMART":          "Supermercado",
    "ACUENTA":          "Supermercado",

    # ── Comida / Restaurantes ───────────────────────────────
    "RESTAURANTE":      "Comida",
    "RESTAURANT":       "Comida",
    "SUSHI":            "Comida",
    "PIZZA":            "Comida",
    "BURGER":           "Comida",
    "MCDONALDS":        "Comida",
    "MC DONALDS":       "Comida",
    "STARBUCKS":        "Comida",
    "DOMINO":           "Comida",
    "SUBWAY":           "Comida",
    "SÁNDWICH":         "Comida",
    "CAVAS PASTEUR":    "Comida",
    "SAKURA":           "Comida",
    "AHUM":             "Comida",
    "KOMAX":            "Comida",
    "POLO":             "Comida",
    "KIOSCO":           "Comida",
    "CAFE":             "Comida",
    "CAFETERIA":        "Comida",
    "PANADERIA":        "Comida",
    "SENCILLO":         "Comida",
    "FUENTE DE SODA":   "Comida",

    # ── Delivery ───────────────────────────────────────────
    "UBER EATS":        "Delivery",
    "PEDIDOS YA":       "Delivery",
    "RAPPI":            "Delivery",

    # ── Transporte ─────────────────────────────────────────
    "UBER":             "Transporte",
    "CABIFY":           "Transporte",
    "BENCIN":           "Transporte",
    "COPEC":            "Transporte",
    "PETROBRAS":        "Transporte",
    "SHELL":            "Transporte",
    "ESSO":             "Transporte",
    "ENEX":             "Transporte",
    "PEAJE":            "Transporte",
    "AUTOPISTA":        "Transporte",
    "TELEPASE":         "Transporte",
    "AUTOPASS":         "Transporte",
    "LAVADO":           "Transporte",
    "ESTACION DE SERV": "Transporte",
    "BICI":             "Transporte",
    "METRO ":           "Transporte",
    "TRANSANTIAGO":     "Transporte",
    "TAXI":             "Transporte",
    "BOOKING.COM":      "Transporte",
    "LATAM":            "Transporte",
    "LAN":              "Transporte",
    "AVIANCA":          "Transporte",
    "SKY AIRLINE":      "Transporte",

    # ── Entretenimiento ────────────────────────────────────
    "NETFLIX":          "Entretenimiento",
    "SPOTIFY":          "Entretenimiento",
    "DISNEY":           "Entretenimiento",
    "HBO":              "Entretenimiento",
    "APPLE.COM":        "Entretenimiento",
    "STEAM":            "Entretenimiento",
    "PLAYSTATION":      "Entretenimiento",
    "XBOX":             "Entretenimiento",
    "CINE":             "Entretenimiento",
    "CINEMA":           "Entretenimiento",
    "TEATRO":           "Entretenimiento",
    "YOUTUBE":          "Entretenimiento",
    "TWITCH":           "Entretenimiento",
    "PRIME VIDEO":      "Entretenimiento",
    "DEEZER":           "Entretenimiento",

    # ── Vida Social / Salidas ──────────────────────────────
    "BAR ":             "Vida Social",
    "DISCOTECA":        "Vida Social",
    "CLUB ":            "Vida Social",
    "BOLICHE":          "Vida Social",
    "PISCO":            "Vida Social",
    "CERVEZA":          "Vida Social",
    "VINOTECA":         "Vida Social",
    "VINOS":            "Vida Social",
    "BOTILLERIA":       "Vida Social",
    "LICORERIA":        "Vida Social",

    # ── Deporte / Salud ────────────────────────────────────
    "GIMNASIO":         "Deporte",
    "GYM":              "Deporte",
    "SMARTFIT":         "Deporte",
    "PLANET FITNESS":   "Deporte",
    "EQUINOX":          "Deporte",
    "YOGA":             "Deporte",
    "CROSSFIT":         "Deporte",
    "RUNNING":          "Deporte",
    "DECATHLON":        "Deporte",
    "FARMACIA":         "Salud",
    "FARMACIAS":        "Salud",
    "CRUZ VERDE":       "Salud",
    "SALCOBRAND":       "Salud",
    "AHUMADA":          "Salud",
    "CLINICA":          "Salud",
    "HOSPITAL":         "Salud",
    "ISAPRE":           "Salud",
    "FONASA":           "Salud",
    "MEDICO":           "Salud",
    "DENTAL":           "Salud",
    "OPTICA":           "Salud",
    "LABORATORIO":      "Salud",

    # ── Vivienda / Hogar ───────────────────────────────────
    "ARRIENDO":         "Vivienda",
    "DIVIDENDO":        "Vivienda",
    "HOMECENTERS":      "Hogar",
    "SODIMAC":          "Hogar",
    "EASY":             "Hogar",
    "IKEA":             "Hogar",
    "PARIS":            "Hogar",
    "FALLABELLA":       "Hogar",
    "FALABELLA":        "Hogar",
    "ABCDIN":           "Hogar",
    "RIPLEY":           "Hogar",
    "LA POLAR":         "Hogar",

    # ── Servicios básicos ──────────────────────────────────
    "METROGAS":         "Servicios",
    "AGUAS":            "Servicios",
    "CHILECTRA":        "Servicios",
    "ENEL":             "Servicios",
    "CGE":              "Servicios",
    "INTERNET":         "Servicios",
    "VTR":              "Servicios",
    "CLARO":            "Servicios",
    "ENTEL":            "Servicios",
    "MOVISTAR":         "Servicios",
    "WOM":              "Servicios",
    "LUZ ":             "Servicios",

    # ── Seguros ────────────────────────────────────────────
    "SEGURO":           "Seguros",
    "INSURANCE":        "Seguros",
    "MAPFRE":           "Seguros",
    "BCI SEGUROS":      "Seguros",
    "LIBERTY":          "Seguros",
    "SURA":             "Seguros",
    "ZURICH":           "Seguros",
    "SOUTHBRIDGE":      "Seguros",
    "HDI":              "Seguros",
    "RENTA 4":          "Seguros",  # préstamos/seguros invers.
    "COM.MANTENCION":   "Seguros",  # comisión banco

    # ── Compras / Retail ───────────────────────────────────
    "AMAZON":           "Compras",
    "MERCADOLIBRE":     "Compras",
    "MERPAGO":          "Compras",
    "ALIEXPRESS":       "Compras",
    "ZARA":             "Compras",
    "H&M":              "Compras",
    "SHEIN":            "Compras",
    "ADIDAS":           "Compras",
    "NIKE":             "Compras",
    "TRICOT":           "Compras",

    # ── Educación ──────────────────────────────────────────
    "UNIVERSIDAD":      "Educación",
    "COLEGIO":          "Educación",
    "CURSO":            "Educación",
    "UDEMY":            "Educación",
    "COURSERA":         "Educación",
    "DUOLINGO":         "Educación",
    "LIBROS":           "Educación",

    # ── Transferencias / Banco ─────────────────────────────
    "TRANSF":           "Transferencia",
    "TRASPASO":         "Transferencia",
    "MONTO CANCELADO":  "Pago tarjeta",
    "NOTA DE CREDITO":  "Abono",
    "ABONO":            "Abono",
    "AFP":              "AFP",
    "COTIZACION":       "AFP",
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
