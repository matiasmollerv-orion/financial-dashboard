# ============================================================
# CATEGORIZACIÓN DE CUENTA CORRIENTE
#
# Estructura paralela a dashboard/categorias.py (gastos TC):
#   - cc_top_level     ("Fixed Costs", "Guilt Free", "Investments",
#                       "Impuestos", "Familia", "Ingresos", "Excluir")
#   - cc_subcategoria  (Matrimonio, Arriendo, Crypto, Compras, etc.)
#   - cc_contabilidad  ("gasto", "ingreso", "excluir", "neutro")
#       gasto    → cuenta como egreso real
#       ingreso  → cuenta como ingreso real
#       excluir  → YA está contado en otra fuente (Pago TC, Inversiones,
#                  traspaso entre cuentas propias) — no doble contar
#       neutro   → familia/pareja/amigos: informativo, no afecta balance
# ============================================================

import re
from typing import Tuple

# Cada regla: (regex, top_level, subcategoria, contabilidad)
REGLAS = [
    # ── PAGO TC PROPIO (excluir — ya está en santander_gastos) ──
    (r"Traspaso.*T\.?\s*Cr[eé]dito|Traspaso Internet a T\. Cr[eé]dito",
     "Fixed Costs", "Pago TC", "excluir"),
    (r"Pago Autom[aá]tico T\. de Cr[eé]dito|Abono Tarjeta|Pago Tarjeta Cr[eé]dito",
     "Fixed Costs", "Pago TC", "excluir"),

    # ── PAGO TC DE OTRO BANCO (excluir, ya está contado en esa otra TC) ──
    (r"TARJETA CMR|CMR Mastercard|PAGO EN LINEA CAT",
     "Fixed Costs", "Pago TC", "excluir"),

    # ── INVERSIONES (excluir — ya están en racional/buda/manuales) ──
    (r"Inversi[oó]n en Fondo Mutuo|Aporte.*Fondo Mutuo|Cargo FM\b",
     "Investments", "Fondos mutuos", "excluir"),
    (r"Traspaso Internet a Cuentam[aá]tica|Cuentam[aá]tica",
     "Investments", "Cuentamática", "excluir"),
    (r"Aporte\s+AFP|Cotizaci[oó]n Previsional",
     "Investments", "AFP", "excluir"),
    (r"PAGO RACIONAL|Racional",
     "Investments", "Racional", "excluir"),
    (r"BUDA|Buda\.com",
     "Investments", "Crypto Buda", "excluir"),
    # Traspasos diarios $3K/$6K a Cuenta de Otro Banco = crypto Buda
    (r"Traspaso a Cuenta de Otro Banco",
     "Investments", "Crypto Buda", "excluir"),
    # Brokers e instituciones
    (r"VECTOR\b|VECTOR CL A|VECTOR CAPITAL",
     "Investments", "Vector", "excluir"),
    (r"RENAISSANCE|XTB CHILE|SANTANDER CORREDORES|KOYWE|Renta 4|\bRENTA 4\b",
     "Investments", "Brokers", "excluir"),
    (r"Smash SpA|SMASH SPA",
     "Investments", "Crypto antiguo", "excluir"),
    (r"Physica PPC|PHYSICA PPC|PHYSICA SPA",
     "Investments", "Inmobiliaria", "excluir"),
    (r"Wallstate|WALLSTATE",
     "Investments", "Inmobiliaria", "excluir"),
    (r"PADEL RINCONADA|PADEL\s+RINCONADA",
     "Investments", "Inmobiliaria", "excluir"),

    # ── TRASPASO ENTRE CUENTAS PROPIAS (excluir — solo mueve plata tuya) ──
    # NOTA: "Transf." con punto Y "Transf a" sin punto, ambos formatos
    (r"Transf\.?\s+(?:a\s+)?Matias\s+Alberto",
     "Excluir", "Traspaso propio", "excluir"),
    (r"Transf\.?\s+(?:a\s+)?Matias\s+(?:Moller|Mario)",
     "Excluir", "Traspaso propio", "excluir"),
    (r"Transf\.?\s+(?:a\s+)?Matias\b(?!\s+(?:Alberto|Moller|Mario))",
     "Excluir", "Traspaso propio", "excluir"),
    (r"Transf\..*Moller Verderau",
     "Excluir", "Traspaso propio", "excluir"),
    (r"Traspaso Internet de Cuenta Vista|Traspaso de Cuenta Vista|Dep[oó]sito.*Vales Vista",
     "Excluir", "Traspaso propio", "excluir"),

    # ── CAMBIO DE DIVISAS (neutro, es conversión no gasto) ──
    (r"Egreso por Compra de Divisas|Compra de Divisas|Compra USD|Compra D[oó]lares",
     "Fixed Costs", "Cambio divisas", "neutro"),
    (r"Venta de Divisas|Venta USD|Venta D[oó]lares|ABONO DE DIVISAS",
     "Fixed Costs", "Cambio divisas", "neutro"),

    # ── COMISIONES BANCARIAS (gasto real) ──
    (r"COM\.MANTENCION|COMISION MANTENCION|MANTENCION PLAN|Cargo Anual",
     "Fixed Costs", "Comisiones", "gasto"),
    (r"COMISION|COBRO SERVICIO|Cuota Manejo",
     "Fixed Costs", "Comisiones", "gasto"),
    (r"NOTA DE CREDITO|N/C\b",
     "Fixed Costs", "Comisiones", "neutro"),
    (r"OPER\.\s*CENT\s+Devolucion|Devoluci[oó]n\b",
     "Fixed Costs", "Comisiones", "neutro"),
    (r"OPER\.\s*CENT\s+Pago de Reemb|Pago de Reembolso",
     "Fixed Costs", "Comisiones", "neutro"),
    (r"OPER\.\s*CENT\s+Retiro",
     "Investments", "Retiro inversión", "excluir"),

    # ── PAGOS A PROVEEDORES (gasto real) ──
    (r"P\.PROVEEDOR|PAGO PROVEEDOR|P\.PROV\b",
     "Fixed Costs", "Pago proveedor", "gasto"),

    # ── EFECTIVO (gasto real) ──
    (r"Giro en Cajero|Cajero Autom[aá]tico|GIRO\s+CAJERO|Retiro Cajero",
     "Guilt Free", "Efectivo", "gasto"),

    # ── SUELDO / INGRESOS LABORALES ──
    (r"SUELDO|Remuneraci[oó]n|Hon\.\s+Profesional|Pago Sueldo|Liquidaci[oó]n",
     "Ingresos", "Sueldo", "ingreso"),
    (r"Mercado Libre.*Sueldo|MLI.*Sueldo|Pago Mercado Libre",
     "Ingresos", "Sueldo", "ingreso"),

    # ── PERSONAS IDENTIFICADAS (orden importa: específicas primero) ──

    # Señora (María Begoña Alarcón)
    (r"MARIA BEGO|MARIA BEGONA",
     "Familia", "Pareja", "neutro"),

    # Suegro (Rene Pablo Alarcón Lillo) - matrimonio
    (r"Rene Pablo Alarcon|RENE PABLO ALARCON",
     "Guilt Free", "Matrimonio", "neutro"),

    # Dueña depto (Veronica Morales) → ARRIENDO
    (r"Veronica Morales|VERONICA MORALES",
     "Fixed Costs", "Arriendo", "gasto"),

    # Carlos Luis AGUILERA → matrimonio (NO familia)
    (r"CARLOS LUIS AGUILERA|CARLOS LUIS AGUI\b",
     "Guilt Free", "Matrimonio", "gasto"),

    # Padre (Carlos Luis Moller, sin Aguilera) y cuenta secundaria Moller Parot
    (r"Transf\.?\s*(?:a\s+)?CARLOS LUI(?!.*AGUILERA)|CARLOS LUIS MOLLER",
     "Familia", "Padre", "neutro"),
    (r"MOLLER PARO|Moller Parot",
     "Familia", "Padre", "neutro"),

    # Familiar Juan Andrés Ruiz Tagle
    (r"Juan Andres Ruiz|JUAN ANDRES RUIZ",
     "Familia", "Familia", "neutro"),

    # Amigo Alejandro Barros
    (r"Alejandro Barros|ALEJANDRO BARROS",
     "Familia", "Amigo", "neutro"),

    # Venta personal (iPad) - Ronny Andrés
    (r"Ronny Andres Gonzalez|RONNY ANDRES GONZALEZ",
     "Ingresos", "Venta personal", "ingreso"),

    # Banquetera matrimonio
    (r"RC BANQUETERIA|BANQUETERIA",
     "Guilt Free", "Matrimonio", "gasto"),

    # Otros familiares con apellido Moller / Verderau / Tomas
    (r"Transf\..*MOLLER\b(?!.*PARO)|Transf\..*VERDERAU|Transf\..*TOMAS|SOFIA MOLLER",
     "Familia", "Familia", "neutro"),

    # ── ARRIENDO / GGCC genérico ──
    (r"ARRIENDO|ARRENDAMIENTO|GASTOS COMUNES|GTO\s+COMUN|CONDOMINIO",
     "Fixed Costs", "Arriendo", "gasto"),

    # ── SERVICIOS BÁSICOS pagados por TEF ──
    (r"ENEL|CGE|CHILECTRA|AGUAS ANDINAS|ESVAL|METROGAS",
     "Fixed Costs", "Servicios", "gasto"),
    (r"ENTEL|CLARO|MOVISTAR|VTR|WOM",
     "Fixed Costs", "Servicios", "gasto"),

    # ── IMPUESTOS / SII ──
    (r"\bSII\b|TESORERIA|IMPUESTO",
     "Impuestos", "Impuestos", "gasto"),

    # ── TRANSFERENCIAS SALIENTES GENÉRICAS (probable gasto/matrimonio) ──
    (r"Transf\.\s+a\b|Transf\.\s+Internet a otro|Transferencia a",
     "Guilt Free", "Transferencia saliente", "gasto"),

    # ── DEFAULT — sin categorizar ──
    (r".*",
     "Sin Categorizar", "Otros", "neutro"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), tl, sub, conta)
             for p, tl, sub, conta in REGLAS]


def categorizar_cuenta(descripcion: str) -> Tuple[str, str, str]:
    """
    Retorna (top_level, subcategoria, contabilidad) para una transferencia.
    """
    if not descripcion:
        return ("Sin Categorizar", "Otros", "neutro")
    d = descripcion.strip()
    for pat, tl, sub, conta in _COMPILED:
        if pat.search(d):
            return (tl, sub, conta)
    return ("Sin Categorizar", "Otros", "neutro")


def categorizar_df(df):
    """Agrega columnas 'cc_top_level', 'cc_subcategoria', 'cc_contabilidad' al DataFrame."""
    import pandas as pd
    if df.empty or "descripcion" not in df.columns:
        return df
    cats = df["descripcion"].apply(categorizar_cuenta)
    df["cc_top_level"]    = cats.apply(lambda x: x[0])
    df["cc_subcategoria"] = cats.apply(lambda x: x[1])
    df["cc_contabilidad"] = cats.apply(lambda x: x[2])
    # Compatibilidad hacia atrás
    df["cc_categoria"]    = df["cc_subcategoria"]
    return df
