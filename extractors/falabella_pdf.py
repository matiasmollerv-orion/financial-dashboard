# ============================================================
# PARSER PDF — Estado de Cuenta CMR Falabella (Cliente Elite)
#
# Estructura del "II. DETALLE" del PDF:
#   COMPRAS NACIONALES / COMPRAS INTERNACIONALES / OTROS
#     LUGAR FECHA DESCRIPCION [T|A] MONTO_OPERACION MONTO_TOTAL_A_PAGAR NN/NN [primer_cargo] [valor_cuota]
#   2.3 Cargos, Comisiones, Impuestos y Abonos
#     S/I FECHA DESCRIPCION [T|A] MONTO_OPERACION MONTO_TOTAL_A_PAGAR NN/NN   (pagos, sin lugar de compra real)
#     FECHA DESCRIPCION MONTO_OPERACION MONTO_TOTAL_A_PAGAR NN/NN [valor_cuota]  (cargos propios del banco, sin lugar/titular)
#
# Usamos siempre "Monto Operación" (primer monto tras la fecha/titular) como
# el monto real del movimiento — es el valor de la transacción en sí,
# positivo para compras y negativo para pagos ("Pago tarjeta cmr").
# ============================================================

import os
import re
from datetime import datetime
from pathlib import Path

import pdfplumber
import pikepdf
import pandas as pd

from dashboard.categorias import categorizar

SECCIONES_COMPRA = ("COMPRAS NACIONALES", "COMPRAS INTERNACIONALES", "OTROS")
SECCION_CARGOS = "2.3 Cargos, Comisiones, Impuestos y Abonos"
FIN_DETALLE = "III. INFORMACIÓN DE PAGO"

# El correo real (EstadodeCuenta@cmr.cl) dice: "utiliza como clave tu RUT sin
# puntos y sin el dígito verificador" — confirmado 2026-09-04: es la MISMA
# clave que Santander (SANTANDER_PDF_PASSWORD), no hace falta un secret nuevo.
# Se deja FALABELLA_PDF_PASSWORD como override opcional por si algún día cambia.
PASSWORD = os.getenv("FALABELLA_PDF_PASSWORD") or os.getenv("SANTANDER_PDF_PASSWORD", "")


def unlock_pdf(pdf_path: Path) -> Path:
    """Desbloquea el PDF si tiene clave. Si no la tiene, lo devuelve tal cual."""
    pdf_path = Path(pdf_path)
    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            pass
        return pdf_path  # no tenia clave
    except pikepdf.PasswordError:
        pass

    unlocked_path = pdf_path.with_stem(pdf_path.stem + "_unlocked")
    if unlocked_path.exists():
        return unlocked_path
    with pikepdf.open(str(pdf_path), password=PASSWORD) as pdf:
        pdf.save(str(unlocked_path))
    print(f"  🔓 Desbloqueado: {unlocked_path.name}")
    return unlocked_path

# Línea con lugar + titular: "Santiago 26/06/2026 Uber eats T 1.967 1.967 01/01 ..."
_RE_CON_LUGAR = re.compile(
    r"^(?P<lugar>\S+)\s+(?P<fecha>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+?)\s+"
    r"(?P<titular>[TA])\s+(?P<monto>-?[\d.]+)\s+-?[\d.]+\s+\d{2}/\d{2}"
)
# Línea sin lugar/titular: "24/07/2026 Servicio administracion 7.147 7.147 01/01 7.147"
_RE_SIN_LUGAR = re.compile(
    r"^(?P<fecha>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+?)\s+"
    r"(?P<monto>-?[\d.]+)\s+-?[\d.]+\s+\d{2}/\d{2}"
)


def _parse_monto(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse_estado_cuenta(pdf_path: Path) -> pd.DataFrame:
    """
    Extrae movimientos del Estado de Cuenta CMR Falabella.
    Retorna DataFrame con columnas: fecha, descripcion, monto, moneda,
    categoria, fuente, archivo. 'monto' viene con signo (negativo = pago
    a la tarjeta, no gasto real) — se categoriza a Fixed Costs/Pago TC
    para excluirse del análisis, igual que en santander_pdf.py.
    """
    pdf_path = Path(pdf_path)
    unlocked = unlock_pdf(pdf_path)
    rows = []
    en_seccion_valida = False

    with pdfplumber.open(str(unlocked)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                if line in SECCIONES_COMPRA or line.startswith(SECCION_CARGOS):
                    en_seccion_valida = True
                    continue
                if line.startswith(FIN_DETALLE):
                    en_seccion_valida = False
                    continue
                if not en_seccion_valida:
                    continue
                if line == "Sin Movimientos" or line.startswith("2.2 Productos"):
                    continue

                m = _RE_CON_LUGAR.match(line) or _RE_SIN_LUGAR.match(line)
                if not m:
                    continue

                try:
                    fecha = datetime.strptime(m.group("fecha"), "%d/%m/%Y").date()
                    monto = _parse_monto(m.group("monto"))
                    descripcion = m.group("desc").strip()
                    if monto == 0 or not descripcion:
                        continue
                    rows.append({
                        "fecha": fecha,
                        "descripcion": descripcion,
                        "monto": monto,
                        "moneda": "CLP",
                        "categoria": categorizar(descripcion)[1],
                        "fuente": "falabella_tarjeta",
                        "archivo": pdf_path.name,
                    })
                except (ValueError, ZeroDivisionError):
                    continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("fecha").reset_index(drop=True)
    print(f"  📄 Falabella CMR: {len(df)} movimientos extraídos")
    return df
