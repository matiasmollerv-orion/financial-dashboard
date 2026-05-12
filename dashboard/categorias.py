# ============================================================
# CATEGORIZACIÓN DE GASTOS — 5 NIVELES
#
# 1. SAVINGS      = ahorro, depósitos a plazo, fondos
# 2. INVESTMENTS  = inversiones (AFP, Racional, Fintual…)
# 3. IMPUESTOS    = SII, municipalidad, contribuciones
# 4. FIXED COSTS  = gastos necesarios / rutinarios
# 5. GUILT FREE   = gastos discrecionales / opcionales
#
# Sin match → "Sin Categorizar" / "Otros"
#
# Orden: de más específico a más genérico.
# La primera regla que coincida gana.
# ============================================================

import re

# ── REGLAS ────────────────────────────────────────────────
# (patron_regex, top_level, subcategoria)
# Se busca con re.search() en la descripción en MAYÚSCULAS

REGLAS = [

    # ── 1. SAVINGS ───────────────────────────────────────
    (r"DEP[OÓ]SITO A PLAZO|DAP\b|AHORRO\b|FONDO EMERG|CUENTA AHORRO|CAE\b",
     "Savings", "Depósito/Ahorro"),
    (r"FONDOS MUTUOS|FONDO MUTUO|FM\b.*SANTANDER|SANTANDER.*\bFM\b",
     "Savings", "Fondo Mutuo"),

    # ── 2. INVESTMENTS ───────────────────────────────────
    (r"AFP|PROVIDA|CUPRUM|CAPITAL AFP|PLANVITAL|MODELO AFP|HABITAT AFP",
     "Investments", "AFP"),
    (r"RACIONAL|FINTUAL|BUDA\.COM|BUDA COM|BTCCHILE|ORIONX",
     "Investments", "Inversión"),
    (r"EUROCAPITAL|COMPASS GROUP|LARRAIN VIAL|BTG PACTUAL|SCOTIA INVEST",
     "Investments", "Inversión"),

    # ── 3. IMPUESTOS ─────────────────────────────────────
    (r"\bSII\b|SERVICIO IMPUEST|TESORERIA GRAL|TESORERIA GENERAL",
     "Impuestos", "SII"),
    (r"MUNICIPALIDAD|PATENTE\b|PERMISO CIRC|PERMISO DE CIRC",
     "Impuestos", "Municipalidad"),
    (r"CONTRIBUCIONES|BIENES RAICES|BIEN.*RAIZ",
     "Impuestos", "Contribuciones"),
    (r"\bTIMBRE\b|IMPUESTO AL TIMBRE",
     "Impuestos", "Timbre"),
    (r"\bIVA\b(?!.*DEVOL)",                      # IVA (no devolución)
     "Impuestos", "IVA"),

    # ── 4. FIXED COSTS ───────────────────────────────────

    # Pago Tarjeta de Crédito
    (r"MONTO CANCELADO|MONTO PAGADO|PAGO MINIMO|ABONO TARJETA",
     "Fixed Costs", "Pago TC"),
    (r"TRASPASO A DEUDA NACIONAL|DEUDA NACIONAL|CARGO DEUDA NACIONAL",
     "Fixed Costs", "Pago TC"),
    (r"\d{1,2}/\d{2}/\d{4}\s+BANCO|\bBANCO\b.*\d{4}",
     "Fixed Costs", "Pago TC"),
    (r"PAGO TARJETA|PAG\.? ?TC\b|PAG CRED|PAGO CRED|PAGO MENSUAL TARJ",
     "Fixed Costs", "Pago TC"),
    (r"PAGO CON KUSHKI|PAGO FACIL|PAGO ONLINE|PAGO RAPIDO",
     "Fixed Costs", "Pago TC"),

    # Comisiones bancarias
    (r"NOTA DE CREDITO|NOTA CREDITO|N/C\b",
     "Fixed Costs", "Comisiones"),
    (r"INTERES\b|INTERESES\b|COMISION\b|COMISIONES\b",
     "Fixed Costs", "Comisiones"),
    (r"MANTENCI[OÓ]N|MANTENCION|CUOTA MANEJO|CARGO ANUAL|COBRO SERVICIO",
     "Fixed Costs", "Comisiones"),
    (r"DEVOLUC|DEVOLUCION|REEMBOLSO|CASHBACK",
     "Fixed Costs", "Comisiones"),
    (r"AVANCE\b|AVANCE Y COMPRA|COMPRA DIVISAS|CUOTA FIJA\b",
     "Fixed Costs", "Comisiones"),
    (r"PUNTO PAGOS|PAGOS MASIVOS|WEF\d+",
     "Fixed Costs", "Comisiones"),

    # Arriendo
    (r"ARRIENDO|ARRIEND|ALQUILER|RENTA INMUEBLE",
     "Fixed Costs", "Arriendo"),

    # Seguros
    (r"SEGUROS?\b|MAPFRE|LIBERTY|HDI\b|METLIFE|SURA SEGURO|BCI SEGURO|BICE VIDA|CONSORCIO|ZURICH|AXA\b|PRIMA\b|DESGRAVAMEN",
     "Fixed Costs", "Seguros"),

    # Gastos Comunes
    (r"GASTOS COMUNES|GTO COMUN|CONDOMINIO|ADMINIST.*EDIF|COPROPIED|PORTERIA|ASEO EDIFIC",
     "Fixed Costs", "GGCC"),

    # Servicios básicos
    (r"ENEL\b|CHILECTRA|CGE\b|LUZ\b|ELECTRICIDAD|AGUAS\b|ESVAL|ESSBIO|EMOS\b|SMAPA|AGUA POTABLE",
     "Fixed Costs", "Servicios"),
    (r"ENTEL\b|CLARO\b|MOVISTAR|WOM\b|VTR\b|GTD\b|TELMEX|INTERNET|TELEFON|FIBRA\b|CABLE\b|MP \*ENTELHOGAR|ENTELHOGAR",
     "Fixed Costs", "Servicios"),
    (r"METROGAS|ABASTIBLE|LIPIGAS|GASCO\b|GAS NATURAL|GNLD|GLP\b",
     "Fixed Costs", "Servicios"),
    (r"NETFLIX|SPOTIFY|AMAZON PRIME|DISNEY\+?|HBO\b|APPLE.*TV|YOUTUBE PREMIUM|PARAMOUNT|CRUNCHYROLL|DEEZER|TIDAL",
     "Fixed Costs", "Servicios"),
    (r"ICLOUD|GOOGLE ONE|GOOGLE STORAGE|DROPBOX|MICROSOFT 365|OFFICE 365|ADOBE\b|ANTIVIRUS|NORTON|MCAFEE",
     "Fixed Costs", "Servicios"),
    (r"DIARIO FINANCIERO|EL MERCURIO|REVISTA\b|SUSCRIPCION\b",
     "Fixed Costs", "Servicios"),
    (r"DANYELA|CAROLINA\b",                       # transferencias a personas de servicio
     "Fixed Costs", "Servicios"),

    # Educación
    (r"UNIVERSIDAD|COLEGIO\b|ESCUELA\b|JARDIN INFANT|ACADEMIA\b|INSTITUTO\b|CAPACITAC|TALLER EDUC",
     "Fixed Costs", "Educación"),
    (r"UDEMY|COURSERA|PLATZI|DUOLINGO|KHAN ACAD|MASTERCLASS|SKILLSHARE",
     "Fixed Costs", "Educación"),
    (r"ARANCEL\b|MATRICULA\b|REGISTRO CIVIL",
     "Fixed Costs", "Educación"),

    # Salud
    (r"CLINICA|CL[IÍ]NICA|HOSPITAL|URGENCIA|ISAPRE|FONASA|PREVISION SALUD|SALUD UC|SALUD.*UC\b",
     "Fixed Costs", "Salud"),
    (r"FARMACIA|FARMACIAS|FARMAVALUE|SALCOBRAND|CRUZ VERDE|FCIA\b|BOTICA|DROGUERIA",
     "Fixed Costs", "Salud"),
    (r"AHUM\b|AHUMADA\b",
     "Fixed Costs", "Salud"),
    (r"C\.? ?VERDE\b|CRUZVERDE",                  # Cruz Verde abreviado en estados de cuenta
     "Fixed Costs", "Salud"),
    (r"DENTIST|DENTAL|ODONTOLOGO|KINESI|PSICOLOG|PSIQUIAT|NUTRICION|OFTALM",
     "Fixed Costs", "Salud"),
    (r"LABORATORIO|LAB CLINICO|EXAMEN\b|ECOGRAF|RAYOS X|RADIOLOG",
     "Fixed Costs", "Salud"),
    (r"OPTICA\b|[OÓ]PTICA\b|LENTES\b|AUDIFONO|ORTODONCIA",
     "Fixed Costs", "Salud"),
    (r"\bDR\b|\bDRA\b|MEDIC[OA]\b|DOCTOR\b",
     "Fixed Costs", "Salud"),
    (r"KNOP\b|MEDICAMENTO|VITAMINA|SUPLEMENTO|SUPLETECH|MUNDO SALUD",
     "Fixed Costs", "Salud"),
    (r"SERVICIOS DE REHABILIT|REHABILITACION|REHABILITAC|TECNOMEDICINA|FONOAUDIOLOG",
     "Fixed Costs", "Salud"),
    (r"BIOTREN",
     "Fixed Costs", "Salud"),

    # Supermercado / Almacén
    (r"JUMBO\b|UNIMARC|SANTA ISABEL|TOTTUS|EKONO|MAYORISTA 10|CENTRAL MAYORISTA",
     "Fixed Costs", "Supermercado"),
    (r"LIDER\b|LIDER\.CL|WALMART",
     "Fixed Costs", "Supermercado"),
    (r"SUPERMERCADO|SUPERMARKET|MINIMARKET|ALMACEN\b|VERDULERIA|CARNICERIA|FERIA\b|MERCADO\b",
     "Fixed Costs", "Supermercado"),
    (r"7VEINTE|7-ELEVEN|SEVEN ELEVEN|OK MARKET",
     "Fixed Costs", "Supermercado"),
    (r"CORNERSHOP|KORNERSHOP",
     "Fixed Costs", "Supermercado"),
    (r"PANADERIA|PASTELERIA\b|ROTISSERIA",
     "Fixed Costs", "Supermercado"),
    (r"\bOH\b",
     "Fixed Costs", "Supermercado"),
    (r"FRUTOS\b|AGROSUPER|LA VEGA",
     "Fixed Costs", "Supermercado"),

    # Delivery comida (necesidad)
    (r"UBER EATS|UBEREATS|PAYU.*UBER EATS",
     "Fixed Costs", "Supermercado"),
    (r"PEDIDOS YA|PEDIDOSYA|RAPPI\b|IFOOD\b|JUSTO\b",
     "Fixed Costs", "Supermercado"),

    # Transporte
    (r"UBER\b|PAYU.*UBER TRIP|PAYU.*UBER\b",
     "Fixed Costs", "Transporte"),
    (r"CABIFY|BEAT\b|DIDI\b|BLIQ\b|INDRIVER",
     "Fixed Costs", "Transporte"),
    (r"AWTO\b",
     "Fixed Costs", "Transporte"),
    (r"WHOOSH",
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
    (r"KLASSIKCAR|KLASS.*CAR",
     "Fixed Costs", "Transporte"),
    (r"GRUPO DHL|DHL EXPRESS|CORREOS CHILE|STARKEN|CHILEXPRESS",
     "Fixed Costs", "Transporte"),
    (r"EXPRESS CASTRO|EXPRESS.*MAITENCILLO",
     "Fixed Costs", "Transporte"),
    (r"PASAJEBUS|PASAJE BUS|COMPRA.*PASAJE|PASAJE.*BUS",
     "Fixed Costs", "Transporte"),

    # ── 5. GUILT FREE ────────────────────────────────────

    # Restaurantes / Vida social
    (r"RESTAURANT|RESTAURAN|CAFETERIA|CAF[EÉ]\b|COFFEE|STARBUCKS|JUAN VALDEZ|BISTRO|BRASSERIE",
     "Guilt Free", "Restoran/Social"),
    (r"PIZZERIA|SUSHI|RAMEN|NIKKEI|CANTINA|TABERNA|CERVECERIA|BREWPUB|FUENTE DE SODA",
     "Guilt Free", "Restoran/Social"),
    (r"CAVAS\b|VINOTECA|CAVISTE|VIÑATERIA|BOTILLERIA|LICORERIA",
     "Guilt Free", "Restoran/Social"),
    (r"SAKURA|CASA LA CRUZ|SEN SAKANA|BEASTY BUTCHERS",
     "Guilt Free", "Restoran/Social"),
    (r"YOUTOPIA",
     "Guilt Free", "Deportes/Bienestar"),
    (r"GASTRONOMIA|GASTRONOMÍA",
     "Guilt Free", "Restoran/Social"),
    (r"DOMINOS|PIZZA HUT|BURGER KING|MC DONALD|MCDONALDS|KFC\b|SUBWAY\b|WENDY|DUNKIN",
     "Guilt Free", "Restoran/Social"),
    (r"HELADERIA|HELADOS?\b",
     "Guilt Free", "Restoran/Social"),
    (r"SANDWICH|BURGER\b|HAMBURGUES|TAQUERIA|TACOS\b",
     "Guilt Free", "Restoran/Social"),
    (r"BAR\b.*DE\b|BAR\b.*Y\b|\bBAR\b$|\bBAR\b\s+[A-Z]",
     "Guilt Free", "Restoran/Social"),
    (r"NENAZO|BAR MANIO|BAR DE RIO|SOCIAL BAR|SUBLIME SANDWICH|GREEN PIZZA|EL INTERNADO",
     "Guilt Free", "Restoran/Social"),
    (r"\bEL TORO\b|DA DINO|CHIRINGO\b|RESTAURANT.*CHIRINGO",
     "Guilt Free", "Restoran/Social"),
    (r"REDELCOM.*FOOD|FOODSERVICE|FOOD SERVICE",
     "Guilt Free", "Restoran/Social"),
    (r"TEATRO\b|CINE\b|CINEMARK|CINEPOLIS|CCP\b|MOVIE|CONCIERTO|SHOW\b|ESPECTACULO|PUNTOTICKET|TICKETMASTER",
     "Guilt Free", "Restoran/Social"),
    (r"MUNICIPAL DE PROVIDENC|TEATRO MUNICIPAL",
     "Guilt Free", "Restoran/Social"),

    # Deportes / Bienestar
    (r"GIMNASIO|GYM\b|SMARTFIT|BODYTECH|FITNESS|PILATES|YOGA\b|CROSSFIT|NATACION",
     "Guilt Free", "Deportes/Bienestar"),
    (r"TENIS\b|PADEL\b|GOLF\b|RUNNING|BOXEO|ESCALADA|CLUB.*TENIS|TENIS.*CLUB|SANTUARI",
     "Guilt Free", "Deportes/Bienestar"),
    (r"EASYCANCHA|EASY CANCHA|CANCHA\b",
     "Guilt Free", "Deportes/Bienestar"),
    (r"FULLTENNIS|FULL TENNIS",
     "Guilt Free", "Deportes/Bienestar"),
    (r"CLUB VITACURA|VITACURA.*CLUB|JMVITACURA|JM.*VITACURA",
     "Guilt Free", "Deportes/Bienestar"),
    (r"NAVKA|CENTRO NAVKA|FLOW.*NAVKA",
     "Guilt Free", "Deportes/Bienestar"),
    (r"\bFIT\b.*CUOTA|TH FIT\b",
     "Guilt Free", "Deportes/Bienestar"),
    (r"SPA\b|MASAJE|PELUQUERIA|BARBERIA|ESTETICA|MANICURE|PEDICURE|DEPILACION",
     "Guilt Free", "Deportes/Bienestar"),
    (r"DECATHLON|BICICLETA|MOUNTAIN BIKE|SURF\b|KAYAK\b|COMMENCAL",
     "Guilt Free", "Deportes/Bienestar"),
    (r"OUTLIFE\b|STOKED\b",
     "Guilt Free", "Deportes/Bienestar"),
    (r"MALL SPORT\b|SPORT\b",
     "Guilt Free", "Deportes/Bienestar"),

    # Viajes
    (r"LATAM\.COM|LATAM\b|SKY AIRLIN|AEROL[IÍ]NEAS|AMERICAN AIR|DELTA AIR|UNITED AIR|IBERIA|AIR CANADA|AIR FRANCE|KLM\b|LUFTHANSA|COPA AIR|AVIANCA|VUELING",
     "Guilt Free", "Viajes"),
    (r"AEROPUERTO|AIRPORT|AEROPORT",
     "Guilt Free", "Viajes"),
    (r"BOOKING\.COM|AIRBNB|EXPEDIA|TRIVAGO|HOTEL\b|HOSTAL\b|CABA[NÑ]A|APART.*HOTEL|HOTELERA",
     "Guilt Free", "Viajes"),
    (r"DESPEGAR|TURISMO\b|AGENCIA VIAJE|TOUR\b|EXCURSION|CRUCERO|FERRY\b|NAVIERA",
     "Guilt Free", "Viajes"),
    (r"KIWI\.COM|DL \*KIWI|MAITENCILLO|APPART H|APPARTHOTEL",
     "Guilt Free", "Viajes"),

    # Compras / Retail
    (r"AMAZON\b|ALIEXPRESS|EBAY\b|SHEIN\b|TEMU\b|MERCADOLIBRE|FALABELLA|RIPLEY|PARIS\b|LA POLAR|CORONA\b|HITES\b",
     "Guilt Free", "Compras"),
    (r"ABCDIN|TRICOT|SPORTEX|LINIO\b",
     "Guilt Free", "Compras"),
    (r"IKEA\b|EASY\b|SODIMAC|HOMECENTER|CONSTRUMART|IMPERIAL\b|FERRETERIA",
     "Guilt Free", "Compras"),
    (r"KITCHEN CENTER|MP \*KITCHEN|KITCHENCENTER",
     "Guilt Free", "Compras"),
    (r"INCHCAPE\b",
     "Guilt Free", "Compras"),
    (r"APPLE\b|APPLE STORE|SAMSUNG\b|PCFACTORY|ELECTR",
     "Guilt Free", "Compras"),
    (r"MERCADOPAGO|MERPAGO|MERCADO PAGO",
     "Guilt Free", "Compras"),
    (r"FPAY\b",
     "Guilt Free", "Compras"),
    (r"CHEK\b|CONECTA2\b",
     "Guilt Free", "Compras"),
    (r"ECOMMERCE|E-COMMERCE",
     "Guilt Free", "Compras"),
    (r"RETAIL\b|TIENDA\b",
     "Guilt Free", "Compras"),
    (r"ROCKFORD|DC \b|DIMALOW",
     "Guilt Free", "Compras"),

    # Ropa / For me
    (r"ZARA\b|H&M\b|FOREVER 21|GAP\b|MANGO\b|ADIDAS|NIKE\b|PUMA\b|REEBOK|FILA\b|CONVERSE|VANS\b|TIMBERLAND|TOMMY|LACOSTE",
     "Guilt Free", "For me"),
    (r"LEVI[S']?\b|LEVIS\b",
     "Guilt Free", "For me"),
    (r"VESTIMENTA|ROPA\b|CALZADO|ZAPATOS|ZAPATILLAS|OUTLET\b|MALL\b",
     "Guilt Free", "For me"),
    (r"JOYERIA|RELOJERIA|OPTIC.*MODA|BOLSO\b|CARTERA\b|ACCESORIO",
     "Guilt Free", "For me"),
    (r"ASICS\b",
     "Guilt Free", "For me"),
    (r"SUPERDRY|NORTH FACE|PATAGONIA\b|AMERICAN EAGLE|SAVILLE ROW|PHANTOM\b",
     "Guilt Free", "For me"),
    (r"FORUS\b|MP \*FORUS",
     "Guilt Free", "For me"),
    (r"MI FOTO|FOTOGRAFIA|FOTO\b",
     "Guilt Free", "For me"),

    # Regalos
    (r"REGALO\b|FLORISTER|FLORES\b|ANTOJERIA|NAVIDAD\b|D[IÍ]A.*MADRE",
     "Guilt Free", "Regalos"),

]

# Compilar patrones una sola vez (case-insensitive)
_COMPILED = [(re.compile(pat, re.IGNORECASE), top, sub) for pat, top, sub in REGLAS]


def categorizar(descripcion: str) -> tuple:
    """
    Retorna (top_level, subcategoria) para la descripción dada.
    Si ninguna regla coincide, retorna ("Sin Categorizar", "Otros").
    """
    if not descripcion or not isinstance(descripcion, str):
        return ("Sin Categorizar", "Otros")
    desc_up = descripcion.upper().strip()
    for pattern, top, sub in _COMPILED:
        try:
            if pattern.search(desc_up):
                return (top, sub)
        except Exception:
            continue
    return ("Sin Categorizar", "Otros")


def categorizar_df(df):
    """
    Agrega columnas 'top_level' y 'subcategoria' a un DataFrame
    que tenga columna 'descripcion'.
    """
    import pandas as pd
    if "descripcion" not in df.columns:
        df["top_level"] = "Sin Categorizar"
        df["subcategoria"] = "Otros"
        return df
    cats = df["descripcion"].apply(categorizar)
    df["top_level"]    = cats.apply(lambda x: x[0])
    df["subcategoria"] = cats.apply(lambda x: x[1])
    return df
