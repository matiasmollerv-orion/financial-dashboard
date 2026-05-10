# ============================================================
# CATEGORIZACIÓN DE GASTOS — 2 NIVELES
# (top_level, subcategoria)  basado en descripción
#
# Orden: de más específico a más genérico.
# La primera regla que coincida gana.
# ============================================================

import re

# ── REGLAS ────────────────────────────────────────────────
# (patron_regex, top_level, subcategoria)
# patron_regex se aplica en MAYÚSCULAS sobre la descripción

REGLAS = [

    # ── INVERSIONES (excluir de vista de gastos) ──────────
    (r"AFP|PROVIDA|CUPRUM|CAPITAL|PLANVITAL|MODELO AFP|HABITAT AFP",
     "Investments", "AFP"),
    (r"RACIONAL|FINTUAL|BUDA\.COM|BUDA COM|BTCCHILE|ORIONX",
     "Investments", "Inversión"),
    (r"EUROCAPITAL|COMPASS|LARRAIN VIAL|BTG PACTUAL|SCOTIA INVEST",
     "Investments", "Inversión"),

    # ── PAGO TARJETA / BANCO ──────────────────────────────
    (r"PAGO TARJETA|PAG\.? ?TC|PAGO TC|PAGO CRED|PAG CRED",
     "Fixed Costs", "Pago TC"),
    (r"TRANSFERENCIA|TRF\b|TRANSF\b|WEBPAY.*PAGO|PAG.*BANCO|CHEQUE",
     "Fixed Costs", "Pago TC"),
    (r"SANTANDER.*PAG|BCI.*PAG|BANCO.*PAG|PAG.*SANTANDER|PAG.*BCI",
     "Fixed Costs", "Pago TC"),
    (r"^ABONO|^PAGO |DEPOSITO CUENTA|DEP CUENTA",
     "Fixed Costs", "Pago TC"),

    # ── SEGUROS ───────────────────────────────────────────
    (r"SEGUROS?|SEGURO|MAPFRE|LIBERTY|HDI |METLIFE|SURA SEGUROS|BCI SEGUROS|BICE VIDA|CONSORCIO|ZURICH|AXA |RSA |SOL[IE]|COMPAÑIA DE SEGUROS",
     "Fixed Costs", "Seguros"),
    (r"PRIMA |PRIMA$|DESGRAVAMEN|INCENDIO|ROBO SEGURO|AUTOMOTRIZ SEG",
     "Fixed Costs", "Seguros"),

    # ── GASTOS COMUNES / CONDOMINIO ───────────────────────
    (r"GASTOS COMUNES|GTO COMUN|GC\.? |CONDOMINIO|ADMINISTRACION.*EDIF|COPROPIED",
     "Fixed Costs", "GGCC"),
    (r"MANTENCIO|ASEO EDIFICIO|PORTERIA",
     "Fixed Costs", "GGCC"),

    # ── ARRIENDO ──────────────────────────────────────────
    (r"ARRIENDO|ARRIEND|ALQUILER|RENTA INMUEBLE",
     "Fixed Costs", "Arriendo"),

    # ── SERVICIOS BÁSICOS ────────────────────────────────
    (r"ENEL|CHILECTRA|CGE |CONAFE|LUZ |ELECTRICIDAD|AGUA POTABLE|AGUAS |ESVAL|ESSBIO|EMOS |SMAPA",
     "Fixed Costs", "Servicios"),
    (r"ENTEL|CLARO |MOVISTAR|WOM |VTR |GTD |TELMEX|TELEFONOS|INTERNET|TELEFONIA|CABLE |FIBRA",
     "Fixed Costs", "Servicios"),
    (r"GAS NATURAL|METROGAS|ABASTIBLE|LIPIGAS|GASCO |GLP |GNLD",
     "Fixed Costs", "Servicios"),
    (r"NETFLIX|SPOTIFY|AMAZON PRIME|DISNEY\+?|HBO |APPLE.*TV|YOUTUBE PREMIUM|PARAMOUNT|CRUNCHYROLL|DEEZER|TIDAL",
     "Fixed Costs", "Servicios"),
    (r"ICLOUD|GOOGLE ONE|GOOGLE STORAGE|DROPBOX|MICROSOFT 365|OFFICE 365|ADOBE|ANTIVIRUS|NORTON|MCAFEE",
     "Fixed Costs", "Servicios"),
    (r"HOSTING|DOMINIO|DIGITALOCEAN|AWS |AZURE |HEROKU|CLOUDFLARE|GODADDY|NAMECHEAP",
     "Fixed Costs", "Servicios"),

    # ── CUENTAS BANCARIAS / COMISIONES ────────────────────
    (r"COMISION|MANTENCIÓN|MANTENCION|CUOTA MANEJO|CARGO ANUAL|MEMBRESÍA|MEMBRESIA|COBRO SERVICIO",
     "Fixed Costs", "Comisión/Impuesto"),
    (r"IVA |IVA$|IMPUESTO|TIMBRE|SII |TESORERIA|MUNICIPALIDAD|PATENTE|PERMISO CIRC",
     "Fixed Costs", "Comisión/Impuesto"),
    (r"ESTADO CUENTA|CERT HISTORIAL|INFORME COMERC",
     "Fixed Costs", "Comisión/Impuesto"),

    # ── SALUD ─────────────────────────────────────────────
    (r"CLINICA|CLÍNICA|HOSPITAL|URGENCIA|POSTA |ISAPRE|FONASA|PREVISION|SALUD|MEDIC|FARMACIA|FARMACIAS|FARMAVALUE|AHUMADA|SALCOBRAND|CRUZ VERDE|KNOP|DR\.|DRA\.",
     "Guilt Free", "Salud"),
    (r"DENTIST|DENTAL|ODONTOLOGO|LABORATORIO|EXAMEN|ECOGRAF|RAYOS X|KINESI|PSICOLOG|PSIQUIAT|NUTRICION|OFTALM|OJOS",
     "Guilt Free", "Salud"),
    (r"OPTICA|ÓPTICA|LENTES|AUDIFONO|ORTOPEDIA|ORTODONCIA",
     "Guilt Free", "Salud"),
    (r"BOTICA|DROGUERIA|MEDICAMENTO|VITAMINA|SUPLEMENTO",
     "Guilt Free", "Salud"),

    # ── DEPORTES / BIENESTAR ──────────────────────────────
    (r"GIMNASIO|GYM |SMARTFIT|BODYTECH|SPORT|FITNESS|PILATES|YOGA|CROSSFIT|NATACION|TENIS|PADEL|GOLF|RUNNING|ATLETISMO|BOXEO|JUDO|KARATE|AIKIDO|ESCALADA",
     "Guilt Free", "Deportes/Bienestar"),
    (r"SPA |MASAJE|BELLEZA|PELUQUERIA|BARBERIA|ESTETICA|MANICURE|PEDICURE|DEPILACION|BRONCEADO",
     "Guilt Free", "Deportes/Bienestar"),
    (r"DECATHLON|TRAIL|BICICLETA|CICLISMO|MOUNTAIN BIKE|SURF|KAYAK|EQUIPO DEPORTIVO",
     "Guilt Free", "Deportes/Bienestar"),

    # ── VIAJES ────────────────────────────────────────────
    (r"LATAM|SKY AIRLIN|AEROLÍNEAS|AMERICAN AIR|DELTA AIR|UNITED AIR|IBERIA|AIR CANADA|AIR FRANCE|KLM |LUFTHANSA|COPA AIR|AVIANCA|VOLARIS|VIVA AIR|JET BLUE|SOUTHWEST|VUELING",
     "Guilt Free", "Viajes"),
    (r"AEROPUERTO|AIRPORT|AEROPORT|BOARDING|CHECK.IN",
     "Guilt Free", "Viajes"),
    (r"BOOKING\.COM|AIRBNB|EXPEDIA|TRIVAGO|TRIPADVISOR|HOTEL|HOSTAL|MOTEL|APART.*HOTEL|CABAÑA|CABANA",
     "Guilt Free", "Viajes"),
    (r"TRIP\.COM|DESPEGAR|VIAJE|TURISMO|EXCURSION|TOUR\b|AGENCIA VIAJE",
     "Guilt Free", "Viajes"),
    (r"CRUCERO|FERRY |NAVIERA|TRANSMARCHILAY",
     "Guilt Free", "Viajes"),

    # ── TRANSPORTE ────────────────────────────────────────
    (r"UBER\b(?!.*EATS)",
     "Guilt Free", "Transporte"),
    (r"CABIFY|BEAT |DIDI |BLIQ|INDRIVER|RIDESHARING",
     "Guilt Free", "Transporte"),
    (r"TAXI|METRO |TRANSANTIAGO|RED (?:MOVILI|BUS)|BIP!|BIP |TUR BUS|PULLMAN|FLOTA|BUS INTER|RECARGA TARJETA|TAG |AUTOPISTA|PEAJE",
     "Guilt Free", "Transporte"),
    (r"ESTACIONAMIENTO|PARKING|PARQUIMETRO|AUTOPISTA CENT|COSTANERA NORTE|VESPUCIO|AMERICO VESPUCIO",
     "Guilt Free", "Transporte"),
    (r"BENCINA|COPEC|ESSO |SHELL |PETROBRAS|ENEX|GASOLINA|COMBUSTIBLE",
     "Guilt Free", "Transporte"),
    (r"REVISIÓN TÉCNICA|REVISION TECNICA|INSPECCION VEHIC|AUTOMOTORA|REPUESTO AUTO|MECANICO|TALLER|LUBRICANT",
     "Guilt Free", "Transporte"),

    # ── RESTAURANTES / VIDA SOCIAL ────────────────────────
    (r"RESTAURANT|RESTAURAN|CAFETERIA|CAFÉ|CAFE |COFFEE|STARBUCKS|JUAN VALDEZ|CAFFE|BISTRO|BRASSERIE|PIZZERIA|SUSHI|RAMEN|SUSHITO|NIKKEI|BAR |CANTINA|TABERNA|CERVECERIA|BREWPUB|DISCO |DISCOTECA|KARAOKE|BOLICHE|FUENTE DE SODA",
     "Guilt Free", "Restoran/Social"),
    (r"DOMINOS|PIZZA HUT|BURGER KING|MC DONALD|MCDONALDS|KFC |SUBWAY |WENDY|TACO BELL|CHILI|APPLEBEE|TGI FRIDAY|IHOP |DUNKIN",
     "Guilt Free", "Restoran/Social"),
    (r"CENAS?|ALMUERZO|DESAYUNO|COMIDA|COCTELERIA|VINO|LICOR|CERVEZA|SPIRITS|PISCO",
     "Guilt Free", "Restoran/Social"),

    # ── DELIVERY / UBER EATS (va a Supermercado/Comida) ───
    (r"UBER EATS|UBEREATS|PEDIDOS YA|PEDIDOSYA|RAPPI|CORNERSHOP|IFOOD|JUSTO APP|DELIVERY|JUSTO\b",
     "Guilt Free", "Supermercado/Comida"),

    # ── SUPERMERCADO / ALMACÉN ────────────────────────────
    (r"JUMBO|LIDER|WALMART|UNIMARC|SANTA ISABEL|TOTTUS|EKONO|EL TRÉBOL|TREBOL|MAYORISTA 10|CENTRAL MAYORISTA|COTO |DISCO |VEA |CARREFOUR|ALDI|LIDL",
     "Guilt Free", "Supermercado/Comida"),
    (r"MERCADO|FERIA|VERDULERIA|CARNICERIA|PANADERIA|PASTELERIA|ROTISSERIA|MINIMARKET|ALMACEN",
     "Guilt Free", "Supermercado/Comida"),
    (r"SUPERMERCADO|SUPERMARKET",
     "Guilt Free", "Supermercado/Comida"),

    # ── ENTRETENIMIENTO ───────────────────────────────────
    (r"CINE|CINEMARK|CINEPOLIS|CCP |MOVIE|TEATRO|CONCIERTO|SHOW |EVENTO|ESPECTACULO|TICKETMASTER|PUNTOTICKET|TELETICKET|FERIA |PARQUE",
     "Guilt Free", "Restoran/Social"),
    (r"STEAM|PLAYSTATION|XBOX|NINTENDO|EPIC GAME|ORIGIN|BLIZZARD|RIOT GAME|TWITCH|GAMING",
     "Guilt Free", "For me"),

    # ── COMPRAS / RETAIL ──────────────────────────────────
    (r"AMAZON|ALIEXPRESS|EBAY|WISH\b|SHEIN|TEMU|MERCADOLIBRE|FALABELLA|RIPLEY|PARIS|LA POLAR|CORONA|HITES|TRICOT|SPORTEX",
     "Guilt Free", "Compras"),
    (r"IKEA|EASY |SODIMAC|HOMECENTER|CONSTRUMART|IMPERIAL |CONSTRUC|FERRETERIA|PLOMERIA|ELECTRICIDAD.*TIENDA",
     "Guilt Free", "Compras"),
    (r"APPLE |APPLE STORE|IPHONE|SAMSUNG|MEDIAMARKT|BOULANGER|BEST BUY|PCFACTORY|ABCDIN|ELECTRO|ELECTRODOMESTICO",
     "Guilt Free", "Compras"),
    (r"ZARA|H&M|FOREVER 21|GAP |TOPSHOP|MANGO |ADIDAS|NIKE |PUMA |REEBOK|FILA |CONVERSE|NEW BALANCE|VANS |TIMBERLAND|TOMMY|POLO|LACOSTE",
     "Guilt Free", "For me"),
    (r"VESTIMENTA|ROPA|CALZADO|ZAPATOS|ZAPATILLAS|ACCESORIO|JOYERIA|RELOJERIA|GAFAS|BOLSO|CARTERA|MALL\b|OUTLET",
     "Guilt Free", "For me"),

    # ── REGALOS ───────────────────────────────────────────
    (r"REGALO|PRESENT|FLORISTER|FLORES |CUMPLEAÑOS|NAVIDAD|DÍA DE LA MADRE|ANTOJERIA|PASTELERIA.*REGALO",
     "Guilt Free", "Regalos"),

    # ── EDUCACIÓN ─────────────────────────────────────────
    (r"UNIVERSIDAD|COLEGIO|ESCUELA|JARDÍN INFANT|JARDIN INFANT|ACADEMIA|INSTITUTO|CAPACITACION|CURSO|SEMINARIO|TALLER EDUC|LIBRERIA|LIBROS|LIBRO\b|PAPELERIA",
     "Fixed Costs", "Educación"),
    (r"UDEMY|COURSERA|PLATZI|DUOLINGO|KHAN ACADEMY|MASTERCLASS|SKILLSHARE",
     "Fixed Costs", "Educación"),

    # ── HOGAR / MASCOTAS ─────────────────────────────────
    (r"MASCOTAS?|PET\b|PETCO|DOGS|CATS|VETERINARIA|VETERINARIO|AGROPECUARIA",
     "Guilt Free", "Compras"),
    (r"HOGAR|HOME |DOMESTICO|MUEBLE|DECORACION|PINTURAS|TAPICERIA",
     "Guilt Free", "Compras"),

    # ── MERCADO PAGO / PAYPAL / WALLET ────────────────────
    (r"MERCADOPAGO|MERPAGO|WEBPAY(?!.*PAG)|FLOW\b|KHIPU|TRANSBANK(?!.*PAG)|PAYPAL|APPLE PAY|GOOGLE PAY",
     "Guilt Free", "Compras"),

    # ── GENÉRICO: SI DICE CARGO / DÉBITO ─────────────────
    (r"^CARGO |^DEBITO |^DEB\b",
     "Guilt Free", "Compras"),
]

# Compilar patrones una sola vez
_COMPILED = [(re.compile(pat, re.IGNORECASE), top, sub) for pat, top, sub in REGLAS]


def categorizar(descripcion: str) -> tuple[str, str]:
    """
    Retorna (top_level, subcategoria) para la descripción dada.
    Si ninguna regla coincide, retorna ("Guilt Free", "Otros").
    """
    if not descripcion or not isinstance(descripcion, str):
        return ("Guilt Free", "Otros")
    desc_up = descripcion.upper()
    for pattern, top, sub in _COMPILED:
        if pattern.search(desc_up):
            return (top, sub)
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
    df["top_level"]   = cats.apply(lambda x: x[0])
    df["subcategoria"] = cats.apply(lambda x: x[1])
    return df
