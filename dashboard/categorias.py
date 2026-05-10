# ============================================================
# CATEGORIZACIÓN DE GASTOS — 2 NIVELES
#
# FIXED COSTS  = gastos necesarios / rutinarios
# GUILT FREE   = gastos discrecionales / opcionales
# INVESTMENTS  = excluir de la vista de gastos
#
# Orden: de más específico a más genérico.
# La primera regla que coincida gana.
# ============================================================

import re

# ── REGLAS ────────────────────────────────────────────────
# (patron_regex, top_level, subcategoria)
# Se busca con re.search() en la descripción en MAYÚSCULAS

REGLAS = [

    # ── INVESTMENTS (excluir de gastos) ──────────────────
    (r"AFP|PROVIDA|CUPRUM|CAPITAL AFP|PLANVITAL|MODELO AFP|HABITAT AFP",
     "Investments", "AFP"),
    (r"RACIONAL|FINTUAL|BUDA\.COM|BUDA COM|BTCCHILE|ORIONX|FINTUAL",
     "Investments", "Inversión"),
    (r"EUROCAPITAL|COMPASS GROUP|LARRAIN VIAL|BTG PACTUAL|SCOTIA INVEST",
     "Investments", "Inversión"),

    # ── PAGO TARJETA DE CRÉDITO ──────────────────────────
    # Descripción tipo "$ 1.234.567 09/01/2025 Banco"
    (r"\d{1,2}/\d{2}/\d{4}\s+BANCO|\bBANCO\b.*\d{4}",
     "Fixed Costs", "Pago TC"),
    (r"PAGO TARJETA|PAG\.? ?TC\b|PAG CRED|PAGO CRED|PAGO MENSUAL TARJ",
     "Fixed Costs", "Pago TC"),
    (r"PAGO CON KUSHKI|PAGO FACIL|PAGO ONLINE|PAGO RAPIDO",
     "Fixed Costs", "Pago TC"),

    # ── INTERESES / COMISIONES / IMPUESTOS ───────────────
    (r"INTERES\b|INTERESES\b|COMISION\b|COMISIONES\b",
     "Fixed Costs", "Comisión/Impuesto"),
    (r"MANTENCI[OÓ]N|MANTENCION|CUOTA MANEJO|CARGO ANUAL|COBRO SERVICIO",
     "Fixed Costs", "Comisión/Impuesto"),
    (r"IMPUESTO|IMPUESTOS|IVA\b|TIMBRE|SII\b|TESORERIA|MUNICIPALIDAD|PATENTE|PERMISO CIRC",
     "Fixed Costs", "Comisión/Impuesto"),
    (r"DEVOLUC|DEVOLUCION|REEMBOLSO|CASHBACK",
     "Fixed Costs", "Comisión/Impuesto"),

    # ── ARRIENDO ─────────────────────────────────────────
    (r"ARRIENDO|ARRIEND|ALQUILER|RENTA INMUEBLE",
     "Fixed Costs", "Arriendo"),

    # ── SEGUROS ──────────────────────────────────────────
    (r"SEGUROS?\b|MAPFRE|LIBERTY|HDI\b|METLIFE|SURA SEGURO|BCI SEGURO|BICE VIDA|CONSORCIO|ZURICH|AXA\b|PRIMA\b|DESGRAVAMEN",
     "Fixed Costs", "Seguros"),

    # ── GASTOS COMUNES / CONDOMINIO ──────────────────────
    (r"GASTOS COMUNES|GTO COMUN|CONDOMINIO|ADMINIST.*EDIF|COPROPIED|PORTERIA|ASEO EDIFIC",
     "Fixed Costs", "GGCC"),

    # ── SERVICIOS BÁSICOS (luz, agua, gas, internet) ─────
    (r"ENEL\b|CHILECTRA|CGE\b|LUZ\b|ELECTRICIDAD|AGUAS\b|ESVAL|ESSBIO|EMOS\b|SMAPA|AGUA POTABLE",
     "Fixed Costs", "Servicios"),
    (r"ENTEL\b|CLARO\b|MOVISTAR|WOM\b|VTR\b|GTD\b|TELMEX|INTERNET|TELEFON|FIBRA\b|CABLE\b",
     "Fixed Costs", "Servicios"),
    (r"METROGAS|ABASTIBLE|LIPIGAS|GASCO\b|GAS NATURAL|GNLD|GLP\b",
     "Fixed Costs", "Servicios"),
    (r"NETFLIX|SPOTIFY|AMAZON PRIME|DISNEY\+?|HBO\b|APPLE.*TV|YOUTUBE PREMIUM|PARAMOUNT|CRUNCHYROLL|DEEZER|TIDAL",
     "Fixed Costs", "Servicios"),
    (r"ICLOUD|GOOGLE ONE|GOOGLE STORAGE|DROPBOX|MICROSOFT 365|OFFICE 365|ADOBE\b|ANTIVIRUS|NORTON|MCAFEE",
     "Fixed Costs", "Servicios"),

    # ── EDUCACIÓN ────────────────────────────────────────
    (r"UNIVERSIDAD|COLEGIO\b|ESCUELA\b|JARDIN INFANT|ACADEMIA\b|INSTITUTO\b|CAPACITAC|TALLER EDUC",
     "Fixed Costs", "Educación"),
    (r"UDEMY|COURSERA|PLATZI|DUOLINGO|KHAN ACAD|MASTERCLASS|SKILLSHARE",
     "Fixed Costs", "Educación"),

    # ── SALUD ────────────────────────────────────────────
    (r"CLINICA|CL[IÍ]NICA|HOSPITAL|URGENCIA|ISAPRE|FONASA|PREVISION SALUD",
     "Fixed Costs", "Salud"),
    (r"FARMACIA|FARMACIAS|FARMAVALUE|SALCOBRAND|CRUZ VERDE|FCIA\b|BOTICA|DROGUERIA",
     "Fixed Costs", "Salud"),
    (r"AHUM\b|AHUMADA\b",   # Farmacia Ahumada (abreviado en muchos estados)
     "Fixed Costs", "Salud"),
    (r"DENTIST|DENTAL|ODONTOLOGO|KINESI|PSICOLOG|PSIQUIAT|NUTRICION|OFTALM",
     "Fixed Costs", "Salud"),
    (r"LABORATORIO|EXAMEN\b|ECOGRAF|RAYOS X|RADIOLOG",
     "Fixed Costs", "Salud"),
    (r"OPTICA\b|[OÓ]PTICA\b|LENTES\b|AUDIFONO|ORTODONCIA",
     "Fixed Costs", "Salud"),
    (r"\bDR\b|\bDRA\b|MEDIC[OA]\b|DOCTOR\b",
     "Fixed Costs", "Salud"),
    (r"KNOP\b|MEDICAMENTO|VITAMINA|SUPLEMENTO|BIOTREN",
     "Fixed Costs", "Salud"),

    # ── SUPERMERCADO / ALMACÉN (Fixed Cost) ──────────────
    (r"JUMBO\b|UNIMARC|SANTA ISABEL|TOTTUS|EKONO|MAYORISTA 10|CENTRAL MAYORISTA",
     "Fixed Costs", "Supermercado"),
    (r"LIDER\b|LIDER\.CL|WALMART",
     "Fixed Costs", "Supermercado"),
    (r"SUPERMERCADO|SUPERMARKET|MINIMARKET|ALMACEN\b|VERDULERIA|CARNICERIA|FERIA\b|MERCADO\b",
     "Fixed Costs", "Supermercado"),
    (r"7VEINTE|7-ELEVEN|SEVEN ELEVEN",       # Tiendas de conveniencia
     "Fixed Costs", "Supermercado"),
    (r"CORNERSHOP",                           # Delivery de super
     "Fixed Costs", "Supermercado"),
    (r"PANADERIA|PASTELERIA\b|ROTISSERIA",
     "Fixed Costs", "Supermercado"),

    # ── DELIVERY COMIDA ──────────────────────────────────
    (r"UBER EATS|UBEREATS|PAYU.*UBER EATS",
     "Fixed Costs", "Supermercado"),
    (r"PEDIDOS YA|PEDIDOSYA|RAPPI\b|IFOOD\b|JUSTO\b",
     "Fixed Costs", "Supermercado"),

    # ── TRANSPORTE (Fixed Cost) ───────────────────────────
    (r"UBER\b|PAYU.*UBER TRIP|PAYU.*UBER\b",
     "Fixed Costs", "Transporte"),
    (r"CABIFY|BEAT\b|DIDI\b|BLIQ\b|INDRIVER",
     "Fixed Costs", "Transporte"),
    (r"AWTO\b",                               # Car sharing chileno
     "Fixed Costs", "Transporte"),
    (r"WHOOSH",                               # Scooters eléctricos
     "Fixed Costs", "Transporte"),
    (r"METRO\b|TRANSANTIAGO|RED BUS|RED MOVILIDAD|BIP\b|TUR BUS|PULLMAN|BUS INTER",
     "Fixed Costs", "Transporte"),
    (r"TAXI\b|REMISE\b|TRANSFER AEROP",
     "Fixed Costs", "Transporte"),
    (r"MUEVO\b|COPEC\b|SHELL\b|PETROBRAS|PRONTO COPEC|ESSO\b|ENEX\b|BENCINA|GASOLINA|COMBUSTIBLE",
     "Fixed Costs", "Transporte"),
    (r"ESTACIONAMIENTO|PARKING\b|PARQUIMETRO|AUTOPISTA|PEAJE\b|COSTANERA|VESPUCIO|AMERICO VES",
     "Fixed Costs", "Transporte"),
    (r"TAG\b|TELEPASS|AUTOPISTA CENT",
     "Fixed Costs", "Transporte"),
    (r"REVISION TECNICA|REVISI[OÓ]N T[EÉ]CNICA|INSPECCION VEHIC|MECANICO|TALLER AUTOM|REPUESTO|KOMAX\b|GRUPO POLO",
     "Fixed Costs", "Transporte"),

    # ── RESTAURANTES / VIDA SOCIAL (Guilt Free) ──────────
    (r"RESTAURANT|RESTAURAN|CAFETERIA|CAF[EÉ]\b|COFFEE|STARBUCKS|JUAN VALDEZ|BISTRO|BRASSERIE",
     "Guilt Free", "Restoran/Social"),
    (r"PIZZERIA|SUSHI|RAMEN|NIKKEI|CANTINA|TABERNA|CERVECERIA|BREWPUB|FUENTE DE SODA",
     "Guilt Free", "Restoran/Social"),
    (r"CAVAS\b|VINOTECA|CAVISTE|VIÑATERIA|BOTILLERIA|LICORERIA",  # vinotecas y botillerías
     "Guilt Free", "Restoran/Social"),
    (r"SAKURA|CASA LA CRUZ|YOUTOPIA",         # restaurantes conocidos del usuario
     "Guilt Free", "Restoran/Social"),
    (r"DOMINOS|PIZZA HUT|BURGER KING|MC DONALD|MCDONALDS|KFC\b|SUBWAY\b|WENDY|DUNKIN",
     "Guilt Free", "Restoran/Social"),
    (r"TEATRO\b|CINE\b|CINEMARK|CINEPOLIS|CCP\b|MOVIE|CONCIERTO|SHOW\b|ESPECTACULO|PUNTOTICKET|TICKETMASTER",
     "Guilt Free", "Restoran/Social"),

    # ── DEPORTES / BIENESTAR (Guilt Free) ────────────────
    (r"GIMNASIO|GYM\b|SMARTFIT|BODYTECH|FITNESS|PILATES|YOGA\b|CROSSFIT|NATACION|CROSSF",
     "Guilt Free", "Deportes/Bienestar"),
    (r"TENIS\b|PADEL\b|GOLF\b|RUNNING|BOXEO|ESCALADA|CLUB.*TENIS|TENIS.*CLUB|SANTUARI",
     "Guilt Free", "Deportes/Bienestar"),
    (r"MALL SPORT|7VEINTE.*MALL|SPORT\b",
     "Guilt Free", "Deportes/Bienestar"),
    (r"OUTLIFE\b",                            # outdoor/aventura
     "Guilt Free", "Deportes/Bienestar"),
    (r"SPA\b|MASAJE|PELUQUERIA|BARBERIA|ESTETICA|MANICURE|PEDICURE|DEPILACION",
     "Guilt Free", "Deportes/Bienestar"),
    (r"DECATHLON|BICICLETA|MOUNTAIN BIKE|SURF\b|KAYAK\b|COMMENCAL",  # bicicletas MTB
     "Guilt Free", "Deportes/Bienestar"),

    # ── VIAJES (Guilt Free) ───────────────────────────────
    (r"LATAM\.COM|LATAM\b|SKY AIRLIN|AEROL[IÍ]NEAS|AMERICAN AIR|DELTA AIR|UNITED AIR|IBERIA|AIR CANADA|AIR FRANCE|KLM\b|LUFTHANSA|COPA AIR|AVIANCA|VUELING",
     "Guilt Free", "Viajes"),
    (r"AEROPUERTO|AIRPORT|AEROPORT",
     "Guilt Free", "Viajes"),
    (r"BOOKING\.COM|AIRBNB|EXPEDIA|TRIVAGO|HOTEL\b|HOSTAL\b|CABAÑA|CABANA|APART.*HOTEL",
     "Guilt Free", "Viajes"),
    (r"DESPEGAR|TURISMO\b|AGENCIA VIAJE|TOUR\b|EXCURSION|CRUCERO|FERRY\b|NAVIERA",
     "Guilt Free", "Viajes"),

    # ── COMPRAS / RETAIL (Guilt Free) ────────────────────
    (r"AMAZON\b|ALIEXPRESS|EBAY\b|SHEIN\b|TEMU\b|MERCADOLIBRE|FALABELLA|RIPLEY|PARIS\b|LA POLAR|CORONA\b|HITES\b",
     "Guilt Free", "Compras"),
    (r"ABCDIN|TRICOT|SPORTEX|LINIO\b",
     "Guilt Free", "Compras"),
    (r"IKEA\b|EASY\b|SODIMAC|HOMECENTER|CONSTRUMART|IMPERIAL\b|FERRETERIA",
     "Guilt Free", "Compras"),
    (r"APPLE\b|APPLE STORE|SAMSUNG\b|PCFACTORY|ABCDIN|ELECTR",
     "Guilt Free", "Compras"),
    (r"MERCADOPAGO|MERPAGO|MERCADO PAGO",     # MercadoPago genérico → Compras
     "Guilt Free", "Compras"),
    (r"CHEK\b|CONECTA2\b",                    # Wallets digitales
     "Guilt Free", "Compras"),

    # ── ROPA / FOR ME (Guilt Free) ────────────────────────
    (r"ZARA\b|H&M\b|FOREVER 21|GAP\b|MANGO\b|ADIDAS|NIKE\b|PUMA\b|REEBOK|FILA\b|CONVERSE|VANS\b|TIMBERLAND|TOMMY|LACOSTE",
     "Guilt Free", "For me"),
    (r"VESTIMENTA|ROPA\b|CALZADO|ZAPATOS|ZAPATILLAS|OUTLET\b|MALL\b",
     "Guilt Free", "For me"),
    (r"JOYERIA|RELOJERIA|OPTIC.*MODA|BOLSO\b|CARTERA\b|ACCESORIO",
     "Guilt Free", "For me"),

    # ── REGALOS (Guilt Free) ──────────────────────────────
    (r"REGALO\b|FLORISTER|FLORES\b|ANTOJERIA|NAVIDAD\b|D[IÍ]A.*MADRE",
     "Guilt Free", "Regalos"),

    # ── SUPERMERCADO adicional ────────────────────────────
    (r"\bOH\b",                               # OH! supermercados
     "Fixed Costs", "Supermercado"),
    (r"FRUTOS\b|AGROSUPER|LA VEGA",
     "Fixed Costs", "Supermercado"),

    # ── RESTAURANTES adicional ────────────────────────────
    (r"SANDWICH|BURGER\b|HAMBURGUES|SUSHI|TAQUERIA|TACOS\b|PASTELERIA\b",
     "Guilt Free", "Restoran/Social"),
    (r"BAR\b.*DE\b|BAR\b.*Y\b|\bBAR\b$|\bBAR\b\s+[A-Z]",
     "Guilt Free", "Restoran/Social"),
    (r"NENAZO|BAR MANIO|BAR DE RIO|SOCIAL BAR|SUBLIME SANDWICH|PHANTOM\b",
     "Guilt Free", "Restoran/Social"),
    (r"STOKED\b",                             # tienda surf/outdoor (estilo restaurante no, es ropa)
     "Guilt Free", "Deportes/Bienestar"),

    # ── ROPA adicional ────────────────────────────────────
    (r"SUPERDRY|NORTH FACE|PATAGONIA\b|AMERICAN EAGLE|SAVILLE ROW|PHANTOM\b",
     "Guilt Free", "For me"),
    (r"FORUS\b|MP \*FORUS",
     "Guilt Free", "For me"),

    # ── DEPORTES adicional ────────────────────────────────
    (r"EASYCANCHA|EASY CANCHA|CANCHA\b",
     "Guilt Free", "Deportes/Bienestar"),
    (r"\bFIT\b.*CUOTA|TH FIT\b",
     "Guilt Free", "Deportes/Bienestar"),

    # ── VIAJES adicional ──────────────────────────────────
    (r"KIWI\.COM|DL \*KIWI|MAITENCILLO|APPART H|APPARTHOTEL",
     "Guilt Free", "Viajes"),
    (r"EXPRESS.*MAITENCILLO",
     "Guilt Free", "Viajes"),

    # ── EDUCACIÓN adicional ───────────────────────────────
    (r"ARANCEL\b|MATRICULA\b|REGISTRO CIVIL",
     "Fixed Costs", "Educación"),

    # ── SALUD adicional ───────────────────────────────────
    (r"REHABILITACION|REHABILITAC|TECNOMEDICINA|FONOAUDIOLOG",
     "Fixed Costs", "Salud"),

    # ── TRANSPORTE adicional ──────────────────────────────
    (r"KLASSIKCAR|KLASS.*CAR",
     "Fixed Costs", "Transporte"),

    # ── COMISIÓN/IMPUESTO adicional ───────────────────────
    (r"PUNTO PAGOS|PAGOS MASIVOS|WEF\d+",
     "Fixed Costs", "Comisión/Impuesto"),

    # ── COMPRAS adicional ─────────────────────────────────
    (r"RETAIL\b|TIENDA\b",
     "Guilt Free", "Compras"),

    # ── GENÉRICO TRANSFERENCIA A PERSONA ─────────────────
    (r"DANYELA|CAROLINA\b",
     "Fixed Costs", "Servicios"),

    # ── AVANCE / CUOTAS ───────────────────────────────────
    (r"AVANCE\b|AVANCE Y COMPRA|COMPRA DIVISAS|CUOTA FIJA\b",
     "Fixed Costs", "Comisión/Impuesto"),
]

# Compilar patrones una sola vez (case-insensitive)
_COMPILED = [(re.compile(pat, re.IGNORECASE), top, sub) for pat, top, sub in REGLAS]


def categorizar(descripcion: str) -> tuple:
    """
    Retorna (top_level, subcategoria) para la descripción dada.
    Si ninguna regla coincide, retorna ("Guilt Free", "Otros").
    """
    if not descripcion or not isinstance(descripcion, str):
        return ("Guilt Free", "Otros")
    desc_up = descripcion.upper().strip()
    for pattern, top, sub in _COMPILED:
        try:
            if pattern.search(desc_up):
                return (top, sub)
        except Exception:
            continue
    return ("Guilt Free", "Otros")


def categorizar_df(df):
    """
    Agrega columnas 'top_level' y 'subcategoria' a un DataFrame
    que tenga columna 'descripcion'.
    """
    import pandas as pd
    if "descripcion" not in df.columns:
        df["top_level"] = "Guilt Free"
        df["subcategoria"] = "Otros"
        return df
    cats = df["descripcion"].apply(categorizar)
    df["top_level"]    = cats.apply(lambda x: x[0])
    df["subcategoria"] = cats.apply(lambda x: x[1])
    return df
