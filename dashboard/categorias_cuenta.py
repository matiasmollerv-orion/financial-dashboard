# ============================================================
# CATEGORIZACIÓN DE CUENTA CORRIENTE
#
# Las transferencias de la cuenta corriente NO son todas gastos.
# Algunas son inversiones (ya contadas en racional/buda),
# pagos de TC (ya contados en santander_gastos), transferencias
# entre cuentas propias (no son ni gasto ni ingreso), etc.
#
# Este módulo categoriza cada transferencia para que el dashboard
# muestre SOLO los gastos reales sin doble contar.
# ============================================================

import re
from typing import Tuple

# Cada regla: (regex, categoria, flag_contabilidad, signo_default)
# flag_contabilidad:
#   - "gasto": cuenta como gasto real (egreso)
#   - "ingreso": cuenta como ingreso (sueldo, devoluciones)
#   - "excluir": no contar (ya está en otra fuente - pago TC, inversiones, traspasos internos)
#   - "neutro": informativo, no afecta balance (transferencias familiares, divisas)
# signo_default: si el monto del PDF viene siempre positivo, asumimos este signo
#   - "+": entra plata (abono)
#   - "-": sale plata (cargo)
#   - "?": ambiguo, requiere lookup del valor original

REGLAS = [
    # ── PAGOS DE TARJETA DE CRÉDITO (excluir, ya están en santander_gastos) ──
    (r"Traspaso.*T\.?\s*Cr[eé]dito|Traspaso Internet a T\. Cr[eé]dito",
     "Pago TC", "excluir", "-"),
    (r"Pago Autom[aá]tico T\. de Cr[eé]dito|Abono Tarjeta|Pago Tarjeta Cr[eé]dito",
     "Pago TC", "excluir", "-"),

    # ── INVERSIONES (excluir, ya están en racional/buda) ──
    (r"Inversi[oó]n en Fondo Mutuo|Aporte.*Fondo Mutuo|Cargo FM\b",
     "Inversión", "excluir", "-"),
    (r"Traspaso Internet a Cuentam[aá]tica|Cuentam[aá]tica",
     "Inversión", "excluir", "-"),
    (r"Aporte\s+AFP|Cotizaci[oó]n Previsional",
     "Inversión", "excluir", "-"),
    (r"PAGO RACIONAL|Racional",
     "Inversión", "excluir", "-"),
    (r"BUDA|Buda\.com",
     "Inversión", "excluir", "-"),

    # ── TRANSFERENCIAS ENTRE CUENTAS PROPIAS (excluir, no es gasto ni ingreso) ──
    (r"Transf\.\s+Matias\s+Alberto|Transf\.\s+Matias\s+Moller|Transf\..*Moller Verderau",
     "Traspaso propio", "excluir", "?"),
    (r"Transf\.\s+Matias\b(?!\s+(?:Alberto|Moller))",
     "Traspaso propio", "excluir", "?"),
    (r"Traspaso Internet de Cuenta Vista|Traspaso de Cuenta Vista",
     "Traspaso propio", "excluir", "+"),

    # ── COMPRA/VENTA DE DIVISAS (neutro - es conversión, no gasto) ──
    (r"Egreso por Compra de Divisas|Compra de Divisas|Compra USD|Compra D[oó]lares",
     "Cambio divisas", "neutro", "-"),
    (r"Venta de Divisas|Venta USD|Venta D[oó]lares",
     "Cambio divisas", "neutro", "+"),

    # ── COMISIONES BANCARIAS (gasto real) ──
    (r"COM\.MANTENCION|COMISION MANTENCION|MANTENCION PLAN|Cargo Anual",
     "Comisiones bancarias", "gasto", "-"),
    (r"COMISION|COBRO SERVICIO|Cuota Manejo",
     "Comisiones bancarias", "gasto", "-"),
    (r"NOTA DE CREDITO|N/C\b",
     "Comisiones bancarias", "neutro", "+"),

    # ── PAGOS A PROVEEDORES (gasto real) ──
    (r"P\.PROVEEDOR|PAGO PROVEEDOR|P\.PROV\b",
     "Pago proveedor", "gasto", "-"),

    # ── EFECTIVO (gasto real, no se sabe en qué) ──
    (r"Giro en Cajero|Cajero Autom[aá]tico|GIRO\s+CAJERO|Retiro Cajero",
     "Efectivo", "gasto", "-"),

    # ── SUELDO / INGRESOS LABORALES (ingreso) ──
    (r"SUELDO|Remuneraci[oó]n|Hon\.\s+Profesional|Pago Sueldo|Liquidaci[oó]n",
     "Sueldo", "ingreso", "+"),
    (r"Mercado Libre.*Sueldo|MLI.*Sueldo|Pago Mercado Libre",
     "Sueldo", "ingreso", "+"),

    # ── TRANSFERENCIAS A TERCEROS (gasto si sale, neutro si conocido) ──
    # Familiares conocidos (transferencias regulares - probablemente no son gastos reales)
    (r"Transf\.\s*MARIA BEGO|Transf\.\s+MARIA BEGONA",
     "Transferencia familia", "neutro", "-"),
    (r"Transf\..*MOLLER\b|Transf\..*VERDERAU|Transf\..*TOMAS",
     "Transferencia familia", "neutro", "-"),
    (r"Transf\..*CARLOS LUI|Transf\..*CARLOS LUIS MOLLER",
     "Transferencia familia", "neutro", "-"),

    # ── ARRIENDO / GGCC (gasto recurrente) ──
    (r"ARRIENDO|ARRENDAMIENTO|GASTOS COMUNES|GTO\s+COMUN|CONDOMINIO",
     "Arriendo/GGCC", "gasto", "-"),

    # ── SERVICIOS BÁSICOS pagados por TEF (gasto) ──
    (r"ENEL|CGE|CHILECTRA|AGUAS ANDINAS|ESVAL|METROGAS",
     "Servicios básicos", "gasto", "-"),
    (r"ENTEL|CLARO|MOVISTAR|VTR|WOM",
     "Servicios básicos", "gasto", "-"),

    # ── OTRAS TRANSFERENCIAS SALIENTES (probable gasto) ──
    (r"Transf\.\s+a\b|Transf\.\s+Internet a otro|Transferencia a",
     "Transferencia saliente", "gasto", "-"),

    # ── DEFAULT — sin categorizar ──
    (r".*",
     "Sin categorizar", "neutro", "?"),
]

# Precompilar
_COMPILED = [(re.compile(p, re.IGNORECASE), c, f, s) for p, c, f, s in REGLAS]


def categorizar_cuenta(descripcion: str) -> Tuple[str, str, str]:
    """
    Retorna (categoria, contabilidad, signo_sugerido) para una transferencia.

    Ejemplos:
        "Traspaso Internet a T. Crédito" → ("Pago TC", "excluir", "-")
        "Inversión en Fondo Mutuo"       → ("Inversión", "excluir", "-")
        "COM.MANTENCION PLAN"            → ("Comisiones bancarias", "gasto", "-")
        "Transf. a MARIA BEGONA"         → ("Transferencia familia", "neutro", "-")
    """
    if not descripcion:
        return ("Sin categorizar", "neutro", "?")
    desc_up = descripcion.strip()
    for pat, cat, conta, signo in _COMPILED:
        if pat.search(desc_up):
            return (cat, conta, signo)
    return ("Sin categorizar", "neutro", "?")


def categorizar_df(df):
    """Agrega columnas 'cc_categoria', 'cc_contabilidad', 'cc_signo' a un DataFrame."""
    import pandas as pd
    if df.empty or "descripcion" not in df.columns:
        return df
    cats = df["descripcion"].apply(categorizar_cuenta)
    df["cc_categoria"]    = cats.apply(lambda x: x[0])
    df["cc_contabilidad"] = cats.apply(lambda x: x[1])
    df["cc_signo"]        = cats.apply(lambda x: x[2])
    return df
