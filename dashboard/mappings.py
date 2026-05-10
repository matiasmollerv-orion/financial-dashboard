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
    # Acciones chilenas
    "BCI": "Acción", "LTM": "Acción", "CENCOSUD": "Acción",
    "PARAUCO": "Acción", "COPEC": "Acción", "CMPC": "Acción",
    "BSANTANDER": "Acción", "CHILE": "Acción", "COLBUN": "Acción",
    "IAM": "Acción", "ENELAM": "Acción", "QUINENCO": "Acción",
    "CAP": "Acción", "SMU": "Acción",
    # Crypto
    "BTC": "Crypto", "ETH": "Crypto",
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
    "VT": "Global",   "VXUS": "Global", "VEU": "Global",
    "IQLT": "Global", "BNDX": "Global", "IGF": "Global",
    "EEM": "Mercados Emergentes", "VWO": "Mercados Emergentes",
    "EWJ": "Japón", "EZU": "Europa",
    "ILF": "Latinoamérica", "INDA": "India",
    "VNM": "Vietnam",
    # Crypto
    "BTC": "Global", "ETH": "Global",
}

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
