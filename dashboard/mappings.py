# ============================================================
# MAPPINGS: tipo de activo y país por ticker
# ============================================================

TIPO_MAP = {
    # ETFs renta variable USA
    "QQQ": "ETF",  "VOO": "ETF",  "VTI": "ETF",  "VT": "ETF",
    "RSP": "ETF",  "ESGV": "ETF", "VTV": "ETF",  "VBR": "ETF",
    "IJR": "ETF",  "QUAL": "ETF", "IQLT": "ETF", "VXUS": "ETF",
    "VEU": "ETF",  "FTEC": "ETF", "ARTY": "ETF", "ROBO": "ETF",
    "PICK": "ETF", "REMX": "ETF", "LIT": "ETF",  "CPER": "ETF",
    "EEM": "ETF",  "VWO": "ETF",  "EWJ": "ETF",  "EWZ": "ETF",
    "EZU": "ETF",  "ILF": "ETF",  "INDA": "ETF", "VNM": "ETF",
    "IGF": "ETF",  "SCHH": "ETF",
    # ETFs renta fija
    "BND": "ETF Renta Fija",  "BNDX": "ETF Renta Fija",
    "IEF": "ETF Renta Fija",  "VGSH": "ETF Renta Fija",
    "VTIP": "ETF Renta Fija", "SCHP": "ETF Renta Fija",
    "TMF": "ETF Renta Fija",
    # ETFs commodities
    "GLDM": "ETF Commodity", "GLD": "ETF Commodity",
    # ETFs crypto
    "BITO": "ETF Crypto",
    # Acciones internacionales
    "ABNB": "Acción", "AMD": "Acción",   "AMZN": "Acción",
    "ANET": "Acción", "APO": "Acción",   "ASML": "Acción",
    "ASTS": "Acción", "AVAV": "Acción",  "AVGO": "Acción",
    "BE":   "Acción", "BJ":   "Acción",  "CCJ":  "Acción",
    "CEG":  "Acción", "CRWD": "Acción",  "FIG":  "Acción",
    "GOOGL":"Acción", "IONQ": "Acción",  "ITUB": "Acción",
    "KKR":  "Acción", "LLY":  "Acción",  "MELI": "Acción",
    "META": "Acción", "MSFT": "Acción",  "MU":   "Acción",
    "NU":   "Acción", "NVDA": "Acción",  "NVO":  "Acción",
    "ONDS": "Acción", "PANW": "Acción",  "PURR": "Acción",
    "PWR":  "Acción", "QUBT": "Acción",  "RGTI": "Acción",
    "SGML": "Acción", "SOFI": "Acción",  "SQM":  "Acción",
    "TSLA": "Acción", "TSM":  "Acción",  "UNH":  "Acción",
    "VCX":  "Acción", "VRT":  "Acción",  "WMT":  "Acción",
    "ZETA": "Acción",
    # Nuevos mayo 2026
    "AMBA": "Acción", "ARES": "Acción", "CRWV": "Acción",
    "LSCC": "Acción", "MP": "Acción",   "NBIS": "Acción",
    "OKLO": "Acción",
    # ETFs nuevos
    "EWY": "ETF", "URNM": "ETF",
    # Acciones chilenas
    "BCI": "Acción", "LTM": "Acción", "CENCOSUD": "Acción",
    "PARAUCO": "Acción", "COPEC": "Acción", "CMPC": "Acción",
    "BSANTANDER": "Acción", "CHILE": "Acción", "COLBUN": "Acción",
    "IAM": "Acción", "ENELAM": "Acción", "QUINENCO": "Acción",
    "CAP": "Acción", "SMU": "Acción",
    "ITAUCL": "Acción", "FALABELLA": "Acción", "CFMITNIPSA": "Fondo Mutuo",
    # Crypto
    "BTC": "Crypto", "ETH": "Crypto",
    # Santander (acciones inputadas)
    "ENELCHILE_STG": "Acción", "ENJOY_STG": "Acción", "LTM_STG": "Acción",
}

PAIS_MAP = {
    # Chile
    "BCI": "Chile", "LTM": "Chile", "CENCOSUD": "Chile",
    "PARAUCO": "Chile", "COPEC": "Chile", "CMPC": "Chile",
    "BSANTANDER": "Chile", "CHILE": "Chile", "COLBUN": "Chile",
    "IAM": "Chile", "ENELAM": "Chile", "QUINENCO": "Chile",
    "CAP": "Chile", "SMU": "Chile", "SQM": "Chile",
    # USA (stocks)
    "ABNB": "EE.UU.", "AMD": "EE.UU.",  "AMZN": "EE.UU.",
    "ANET": "EE.UU.", "APO": "EE.UU.",  "ASTS": "EE.UU.",
    "AVAV": "EE.UU.", "AVGO": "EE.UU.", "BE": "EE.UU.",
    "BJ": "EE.UU.",   "CEG": "EE.UU.",  "CRWD": "EE.UU.",
    "FIG": "EE.UU.",  "GOOGL": "EE.UU.","IONQ": "EE.UU.",
    "KKR": "EE.UU.",  "LLY": "EE.UU.",  "META": "EE.UU.",
    "MSFT": "EE.UU.", "MU": "EE.UU.",   "NVDA": "EE.UU.",
    "ONDS": "EE.UU.", "PANW": "EE.UU.", "PURR": "EE.UU.",
    "PWR": "EE.UU.",  "QUBT": "EE.UU.", "RGTI": "EE.UU.",
    "SOFI": "EE.UU.", "TSLA": "EE.UU.", "UNH": "EE.UU.",
    "VCX": "EE.UU.",  "VRT": "EE.UU.",  "WMT": "EE.UU.",
    "ZETA": "EE.UU.", "CCJ": "EE.UU.",
    # Nuevos mayo 2026
    "AMBA": "EE.UU.", "ARES": "EE.UU.", "CRWV": "EE.UU.",
    "LSCC": "EE.UU.", "MP": "EE.UU.",   "NBIS": "EE.UU.",
    "OKLO": "EE.UU.",
    # USA (ETFs domiciliados en USA)
    "QQQ": "EE.UU.", "VOO": "EE.UU.", "VTI": "EE.UU.",
    "RSP": "EE.UU.", "ESGV": "EE.UU.", "VTV": "EE.UU.",
    "VBR": "EE.UU.", "IJR": "EE.UU.",  "QUAL": "EE.UU.",
    "FTEC": "EE.UU.","ARTY": "EE.UU.", "PICK": "EE.UU.",
    "REMX": "EE.UU.","LIT": "EE.UU.",  "CPER": "EE.UU.",
    "GLDM": "EE.UU.","BITO": "EE.UU.", "SCHH": "EE.UU.",
    "BND": "EE.UU.", "IEF": "EE.UU.",  "VGSH": "EE.UU.",
    "VTIP": "EE.UU.","SCHP": "EE.UU.", "TMF": "EE.UU.",
    # Países Bajos
    "ASML": "Países Bajos",
    # Brasil
    "ITUB": "Brasil", "EWZ": "Brasil",
    # Taiwan
    "TSM": "Taiwán",
    # Noruega/Dinamarca
    "NVO": "Dinamarca",
    # Argentina/Latam
    "MELI": "Latinoamérica", "NU": "Brasil",
    "SGML": "Canadá", "CCJ": "Canadá",
    # Fondos / Internacionales diversificados
    "VT": "Global Diversificado",   "VXUS": "Global ex-USA", "VEU": "Global ex-USA",
    "IQLT": "Global Desarrollado", "BNDX": "Bonos Globales", "IGF": "Infraestructura Global",
    "EEM": "Mercados Emergentes", "VWO": "Mercados Emergentes",
    "EWJ": "Japón", "EZU": "Europa",
    "ILF": "Latinoamérica", "INDA": "India",
    "VNM": "Vietnam",
    "EWY": "Corea del Sur", "URNM": "EE.UU.",
    # Chile
    "ITAUCL": "Chile", "FALABELLA": "Chile", "CFMITNIPSA": "Chile",
    # Crypto
    "BTC": "Criptomonedas", "ETH": "Criptomonedas",
    # Santander (acciones inputadas)
    "ENELCHILE_STG": "Chile", "ENJOY_STG": "Chile", "LTM_STG": "Chile",
}

# ── SECTOR MAP ────────────────────────────────────────────
SECTOR_MAP = {
    # Tecnología
    "AMD": "Tecnología", "NVDA": "Tecnología", "MSFT": "Tecnología",
    "GOOGL": "Tecnología", "META": "Tecnología", "AVGO": "Tecnología",
    "ANET": "Tecnología", "MU": "Tecnología", "TSM": "Tecnología",
    "ASML": "Tecnología", "IONQ": "Tecnología", "QUBT": "Tecnología",
    "RGTI": "Tecnología", "ONDS": "Tecnología", "VRT": "Tecnología",
    "ZETA": "Tecnología", "FTEC": "ETF Tech",
    # Software / Cloud
    "CRWD": "Software/Cloud", "PANW": "Software/Cloud",
    # E-commerce / Consumo
    "AMZN": "E-commerce/Consumo", "MELI": "E-commerce/Consumo",
    "ABNB": "E-commerce/Consumo", "WMT": "E-commerce/Consumo",
    "BJ": "E-commerce/Consumo", "SOFI": "Fintech",
    # Finanzas
    "KKR": "Finanzas", "APO": "Finanzas", "FIG": "Finanzas",
    "NU": "Fintech", "ITUB": "Finanzas",
    # Salud / Biotech
    "UNH": "Salud", "LLY": "Salud", "NVO": "Salud",
    # Energía / Recursos
    "CEG": "Energía/Nuclear", "CCJ": "Energía/Nuclear",
    "BE": "Energía Limpia", "SGML": "Minería/Litio",
    "SQM": "Minería/Litio", "COPEC": "Energía",
    "COLBUN": "Energía", "ENELAM": "Energía", "IAM": "Energía",
    # Defensa / Aeroespacial
    "AVAV": "Defensa", "ASTS": "Defensa/Espacio",
    "PWR": "Infraestructura",
    # Retail/Real Estate Chile
    "CENCOSUD": "Retail Chile", "PARAUCO": "Real Estate Chile",
    "SMU": "Retail Chile", "LTM": "Aviación",
    "CHILE": "Banca Chile", "BCI": "Banca Chile",
    "BSANTANDER": "Banca Chile", "CMPC": "Forestal/Papel",
    "CAP": "Minería", "QUINENCO": "Holding",
    # ETFs por sector
    "QQQ": "ETF Nasdaq 100", "VOO": "ETF S&P 500", "VTI": "ETF Mercado USA",
    "VT": "ETF Global", "VXUS": "ETF ex-USA", "VEU": "ETF ex-USA",
    "RSP": "ETF S&P 500 EW", "ESGV": "ETF ESG", "VTV": "ETF Value",
    "VBR": "ETF Small Cap", "IJR": "ETF Small Cap",
    "QUAL": "ETF Quality", "IQLT": "ETF Quality Intl",
    "ARTY": "ETF AI/Robótica", "ROBO": "ETF Robótica",
    "PICK": "ETF Minería", "REMX": "ETF Metales Raros",
    "LIT": "ETF Litio", "CPER": "ETF Cobre",
    "EEM": "ETF Emergentes", "VWO": "ETF Emergentes",
    "EWJ": "ETF Japón", "EWZ": "ETF Brasil",
    "EZU": "ETF Europa", "ILF": "ETF Latam",
    "INDA": "ETF India", "VNM": "ETF Vietnam",
    "IGF": "ETF Infraestructura", "SCHH": "ETF Real Estate",
    "BND": "ETF Bonos USA", "BNDX": "ETF Bonos Globales",
    "IEF": "ETF Bonos 7-10Y", "VGSH": "ETF Bonos 1-3Y",
    "VTIP": "ETF TIPS", "SCHP": "ETF TIPS", "TMF": "ETF Bonos 20Y 3x",
    "GLDM": "ETF Oro", "GLD": "ETF Oro",
    "BITO": "ETF Crypto",
    "EWY": "ETF Corea", "URNM": "ETF Uranio",
    # Crypto
    "BTC": "Crypto", "ETH": "Crypto",
    # Nuevos mayo 2026
    "AMBA": "Tecnología", "ARES": "Finanzas", "CRWV": "IA/GPU",
    "LSCC": "Tecnología", "MP": "Minería", "NBIS": "IA/GPU",
    "OKLO": "Energía/Nuclear", "TSLA": "Automotriz/EV",
    # Chile nuevos
    "ITAUCL": "Banca Chile", "FALABELLA": "Retail Chile",
    "CFMITNIPSA": "Fondo Mutuo Chile",
    # Santander STG
    "ENELCHILE_STG": "Energía", "ENJOY_STG": "Entretenimiento",
    "LTM_STG": "Aviación",
    # Otros
    "PURR": "Otro", "VCX": "Otro",
}


def get_sector(ticker: str, tipo: str = "") -> str:
    t = ticker.upper()
    if t in SECTOR_MAP:
        return SECTOR_MAP[t]
    # Fallback por tipo
    if "Renta Fija" in tipo:
        return "Renta Fija"
    if "Commodity" in tipo:
        return "Commodity"
    if "Crypto" in tipo:
        return "Crypto"
    if tipo == "ETF":
        return "ETF Diversificado"
    return "Otro"


def get_tipo(ticker: str, mercado: str = "") -> str:
    if mercado == "crypto":
        return "Crypto"
    return TIPO_MAP.get(ticker.upper(), "Acción" if mercado == "nacional" else "ETF")

def get_pais(ticker: str, mercado: str = "") -> str:
    if mercado == "crypto":
        return "Global"
    if mercado == "nacional":
        return "Chile"
    return PAIS_MAP.get(ticker.upper(), "EE.UU.")
