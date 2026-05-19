# ============================================================
# CARTERA BASE — SNAPSHOT INMUTABLE AL 2026-04-30
#
# Esta es la fuente de verdad de la cartera ANTES de aplicar
# movimientos posteriores de Racional/Buda.
#
# update_cartera.py lee de aquí (no de Supabase) para evitar
# multiplicar deltas si el script corre múltiples veces.
#
# Solo modificar cuando se haga un nuevo snapshot manual.
# ============================================================

SNAPSHOT_DATE = "2026-04-30"

# Rentabilidad TWR reportada por Racional al SNAPSHOT_DATE (en %)
# Usa este valor de PARTIDA para componer con el TWR calculado desde snapshot hasta hoy.
# Editable: si Racional reporta hoy 46% pero al 30/04/2026 era 47.5%, pon 47.5.
TWR_PRE_SNAPSHOT_PCT = 46.0

# Acciones chilenas (Racional Portafolio CL)
ACCIONES_CL = [
    {"ticker": "BCI",       "empresa": "Banco de Crédito e Inversiones", "mercado": "nacional", "cantidad": 30.0,     "precio_compra": 23930.43, "precio_actual": 60800.00, "moneda": "CLP"},
    {"ticker": "LTM",       "empresa": "LATAM Airlines Group",           "mercado": "nacional", "cantidad": 83901.0,  "precio_compra": 19.01,    "precio_actual": 21.40,    "moneda": "CLP"},
    {"ticker": "CENCOSUD",  "empresa": "Cencosud",                       "mercado": "nacional", "cantidad": 649.0,    "precio_compra": 1970.25,  "precio_actual": 2275.00,  "moneda": "CLP"},
    {"ticker": "PARAUCO",   "empresa": "Parque Arauco",                  "mercado": "nacional", "cantidad": 341.0,    "precio_compra": 2977.37,  "precio_actual": 4020.00,  "moneda": "CLP"},
    {"ticker": "COPEC",     "empresa": "Empresas Copec",                 "mercado": "nacional", "cantidad": 170.0,    "precio_compra": 6536.42,  "precio_actual": 6303.00,  "moneda": "CLP"},
    {"ticker": "CMPC",      "empresa": "CMPC",                           "mercado": "nacional", "cantidad": 771.0,    "precio_compra": 1397.92,  "precio_actual": 1116.10,  "moneda": "CLP"},
    {"ticker": "BSANTANDER","empresa": "Banco Santander Chile",          "mercado": "nacional", "cantidad": 8916.0,   "precio_compra": 63.16,    "precio_actual": 71.95,    "moneda": "CLP"},
    {"ticker": "CHILE",     "empresa": "Banco de Chile",                 "mercado": "nacional", "cantidad": 3396.0,   "precio_compra": 163.59,   "precio_actual": 168.68,   "moneda": "CLP"},
    {"ticker": "COLBUN",    "empresa": "Colbún",                         "mercado": "nacional", "cantidad": 4159.0,   "precio_compra": 147.63,   "precio_actual": 134.00,   "moneda": "CLP"},
    {"ticker": "IAM",       "empresa": "Inversiones Aguas Metropolitanas","mercado": "nacional","cantidad": 246.0,    "precio_compra": 941.36,   "precio_actual": 980.00,   "moneda": "CLP"},
    {"ticker": "ENELAM",    "empresa": "Enel Américas",                  "mercado": "nacional", "cantidad": 1810.0,   "precio_compra": 87.04,    "precio_actual": 84.00,    "moneda": "CLP"},
    {"ticker": "QUINENCO",  "empresa": "Quinenco",                       "mercado": "nacional", "cantidad": 25.0,     "precio_compra": 3366.15,  "precio_actual": 4400.00,  "moneda": "CLP"},
    {"ticker": "CAP",       "empresa": "CAP",                            "mercado": "nacional", "cantidad": 9.0,      "precio_compra": 6631.88,  "precio_actual": 7015.00,  "moneda": "CLP"},
    {"ticker": "SMU",       "empresa": "SMU",                            "mercado": "nacional", "cantidad": 228.0,    "precio_compra": 160.85,   "precio_actual": 136.64,   "moneda": "CLP"},
]

# Stocks internacionales (Racional Internacional)
STOCKS_INTL = [
    {"ticker": "ABNB",  "empresa": "Airbnb",                    "mercado": "internacional", "cantidad": 0.0903204,   "precio_compra": 120.57,  "precio_actual": 140.36,   "moneda": "USD"},
    {"ticker": "AMD",   "empresa": "Advanced Micro Devices",    "mercado": "internacional", "cantidad": 2.64766673,  "precio_compra": 202.54,  "precio_actual": 354.49,   "moneda": "USD"},
    {"ticker": "AMZN",  "empresa": "Amazon",                    "mercado": "internacional", "cantidad": 6.59532723,  "precio_compra": 220.78,  "precio_actual": 265.06,   "moneda": "USD"},
    {"ticker": "ANET",  "empresa": "Arista Networks",           "mercado": "internacional", "cantidad": 0.95919944,  "precio_compra": 141.73,  "precio_actual": 172.71,   "moneda": "USD"},
    {"ticker": "APO",   "empresa": "Apollo Global Management",  "mercado": "internacional", "cantidad": 2.66412468,  "precio_compra": 112.61,  "precio_actual": 128.72,   "moneda": "USD"},
    {"ticker": "ARTY",  "empresa": "iShares Future AI & Tech",  "mercado": "internacional", "cantidad": 7.40141753,  "precio_compra": 0.00,    "precio_actual": 61.94,    "moneda": "USD"},
    {"ticker": "ASML",  "empresa": "ASML Holding",              "mercado": "internacional", "cantidad": 0.23897301,  "precio_compra": 794.99,  "precio_actual": 1438.99,  "moneda": "USD"},
    {"ticker": "ASTS",  "empresa": "AST SpaceMobile",           "mercado": "internacional", "cantidad": 8.20927508,  "precio_compra": 96.24,   "precio_actual": 73.90,    "moneda": "USD"},
    {"ticker": "AVAV",  "empresa": "AeroVironment",             "mercado": "internacional", "cantidad": 0.83414211,  "precio_compra": 281.35,  "precio_actual": 195.02,   "moneda": "USD"},
    {"ticker": "AVGO",  "empresa": "Broadcom",                  "mercado": "internacional", "cantidad": 0.29315041,  "precio_compra": 351.59,  "precio_actual": 417.43,   "moneda": "USD"},
    {"ticker": "BE",    "empresa": "Bloom Energy",              "mercado": "internacional", "cantidad": 4.28061226,  "precio_compra": 186.89,  "precio_actual": 283.36,   "moneda": "USD"},
    {"ticker": "BITO",  "empresa": "ProShares Bitcoin ETF",     "mercado": "internacional", "cantidad": 3.51370344,  "precio_compra": 0.00,    "precio_actual": 10.47,    "moneda": "USD"},
    {"ticker": "BJ",    "empresa": "BJ's Wholesale Club",       "mercado": "internacional", "cantidad": 2.04081632,  "precio_compra": 98.00,   "precio_actual": 93.89,    "moneda": "USD"},
    {"ticker": "BND",   "empresa": "Vanguard Total Bond Market","mercado": "internacional", "cantidad": 35.98412489, "precio_compra": 73.26,   "precio_actual": 73.50,    "moneda": "USD"},
    {"ticker": "BNDX",  "empresa": "Vanguard Total Intl Bond",  "mercado": "internacional", "cantidad": 27.19200564, "precio_compra": 49.26,   "precio_actual": 48.05,    "moneda": "USD"},
    {"ticker": "CCJ",   "empresa": "Cameco Corp",               "mercado": "internacional", "cantidad": 6.45594737,  "precio_compra": 100.37,  "precio_actual": 123.04,   "moneda": "USD"},
    {"ticker": "CEG",   "empresa": "Constellation Energy",      "mercado": "internacional", "cantidad": 0.42719485,  "precio_compra": 340.76,  "precio_actual": 313.00,   "moneda": "USD"},
    {"ticker": "CPER",  "empresa": "US Commodity Index Copper", "mercado": "internacional", "cantidad": 21.58332203, "precio_compra": 28.34,   "precio_actual": 36.53,    "moneda": "USD"},
    {"ticker": "CRWD",  "empresa": "CrowdStrike",               "mercado": "internacional", "cantidad": 0.52160284,  "precio_compra": 384.99,  "precio_actual": 445.75,   "moneda": "USD"},
    {"ticker": "EEM",   "empresa": "iShares MSCI Emg Mkt ETF",  "mercado": "internacional", "cantidad": 8.73965691,  "precio_compra": 39.64,   "precio_actual": 63.99,    "moneda": "USD"},
    {"ticker": "ESGV",  "empresa": "Vanguard ESG US Stock ETF", "mercado": "internacional", "cantidad": 9.2276047,   "precio_compra": 79.60,   "precio_actual": 125.77,   "moneda": "USD"},
    {"ticker": "EWJ",   "empresa": "iShares MSCI Japan ETF",    "mercado": "internacional", "cantidad": 12.21940612, "precio_compra": 26.47,   "precio_actual": 89.10,    "moneda": "USD"},
    {"ticker": "EWZ",   "empresa": "iShares MSCI Brazil ETF",   "mercado": "internacional", "cantidad": 0.69127785,  "precio_compra": 31.83,   "precio_actual": 39.70,    "moneda": "USD"},
    {"ticker": "EZU",   "empresa": "iShares MSCI Eurozone ETF", "mercado": "internacional", "cantidad": 7.88711131,  "precio_compra": 0.00,    "precio_actual": 66.62,    "moneda": "USD"},
    {"ticker": "FIG",   "empresa": "Figma",                     "mercado": "internacional", "cantidad": 79.00836846, "precio_compra": 58.00,   "precio_actual": 17.70,    "moneda": "USD"},
    {"ticker": "FTEC",  "empresa": "Fidelity MSCI Info Tech",   "mercado": "internacional", "cantidad": 1.76586699,  "precio_compra": 131.72,  "precio_actual": 246.31,   "moneda": "USD"},
    {"ticker": "GLDM",  "empresa": "SPDR Gold MiniShares",      "mercado": "internacional", "cantidad": 8.56828609,  "precio_compra": 79.17,   "precio_actual": 91.37,    "moneda": "USD"},
    {"ticker": "GOOGL", "empresa": "Alphabet",                  "mercado": "internacional", "cantidad": 11.2614176,  "precio_compra": 153.75,  "precio_actual": 384.80,   "moneda": "USD"},
    {"ticker": "IEF",   "empresa": "iShares 7-10yr Treasury",   "mercado": "internacional", "cantidad": 17.00471801, "precio_compra": 94.68,   "precio_actual": 94.98,    "moneda": "USD"},
    {"ticker": "IGF",   "empresa": "iShares Global Infra ETF",  "mercado": "internacional", "cantidad": 1.3777492,   "precio_compra": 60.97,   "precio_actual": 68.53,    "moneda": "USD"},
    {"ticker": "IJR",   "empresa": "iShares Core S&P Small Cap","mercado": "internacional", "cantidad": 1.89089533,  "precio_compra": 105.77,  "precio_actual": 137.10,   "moneda": "USD"},
    {"ticker": "ILF",   "empresa": "iShares Latin America 40",  "mercado": "internacional", "cantidad": 17.44405997, "precio_compra": 26.01,   "precio_actual": 36.44,    "moneda": "USD"},
    {"ticker": "INDA",  "empresa": "iShares MSCI India ETF",    "mercado": "internacional", "cantidad": 35.59990944, "precio_compra": 49.73,   "precio_actual": 49.42,    "moneda": "USD"},
    {"ticker": "IONQ",  "empresa": "IonQ",                      "mercado": "internacional", "cantidad": 7.42724922,  "precio_compra": 57.89,   "precio_actual": 45.12,    "moneda": "USD"},
    {"ticker": "IQLT",  "empresa": "iShares MSCI Intl Quality", "mercado": "internacional", "cantidad": 23.38699869, "precio_compra": 42.76,   "precio_actual": 48.85,    "moneda": "USD"},
    {"ticker": "ITUB",  "empresa": "Itaú Unibanco",             "mercado": "internacional", "cantidad": 59.55167656, "precio_compra": 5.35,    "precio_actual": 8.70,     "moneda": "USD"},
    {"ticker": "KKR",   "empresa": "KKR & Co",                  "mercado": "internacional", "cantidad": 4.26803546,  "precio_compra": 93.72,   "precio_actual": 104.34,   "moneda": "USD"},
    {"ticker": "LIT",   "empresa": "Global X Lithium Battery",  "mercado": "internacional", "cantidad": 6.99028483,  "precio_compra": 0.00,    "precio_actual": 88.24,    "moneda": "USD"},
    {"ticker": "LLY",   "empresa": "Eli Lilly",                 "mercado": "internacional", "cantidad": 2.88985476,  "precio_compra": 763.88,  "precio_actual": 934.60,   "moneda": "USD"},
    {"ticker": "MELI",  "empresa": "MercadoLibre",              "mercado": "internacional", "cantidad": 1.18978797,  "precio_compra": 1897.29, "precio_actual": 1792.63,  "moneda": "USD"},
    {"ticker": "META",  "empresa": "Meta Platforms",            "mercado": "internacional", "cantidad": 1.50828212,  "precio_compra": 459.72,  "precio_actual": 611.91,   "moneda": "USD"},
    {"ticker": "MSFT",  "empresa": "Microsoft",                 "mercado": "internacional", "cantidad": 0.11658847,  "precio_compra": 411.70,  "precio_actual": 407.78,   "moneda": "USD"},
    {"ticker": "MU",    "empresa": "Micron Technology",         "mercado": "internacional", "cantidad": 0.26881358,  "precio_compra": 318.77,  "precio_actual": 517.16,   "moneda": "USD"},
    {"ticker": "NU",    "empresa": "Nu Holdings",               "mercado": "internacional", "cantidad": 337.26659577,"precio_compra": 13.03,   "precio_actual": 14.48,    "moneda": "USD"},
    {"ticker": "NVDA",  "empresa": "Nvidia",                    "mercado": "internacional", "cantidad": 1.90135958,  "precio_compra": 210.42,  "precio_actual": 199.57,   "moneda": "USD"},
    {"ticker": "NVO",   "empresa": "Novo Nordisk",              "mercado": "internacional", "cantidad": 7.84447246,  "precio_compra": 31.87,   "precio_actual": 42.22,    "moneda": "USD"},
    {"ticker": "ONDS",  "empresa": "Ondas Holdings",            "mercado": "internacional", "cantidad": 47.44368323, "precio_compra": 10.17,   "precio_actual": 10.04,    "moneda": "USD"},
    {"ticker": "PANW",  "empresa": "Palo Alto Networks",        "mercado": "internacional", "cantidad": 0.28645233,  "precio_compra": 167.57,  "precio_actual": 179.32,   "moneda": "USD"},
    {"ticker": "PICK",  "empresa": "iShares MSCI Global Metals","mercado": "internacional", "cantidad": 1.05701068,  "precio_compra": 29.40,   "precio_actual": 61.60,    "moneda": "USD"},
    {"ticker": "PURR",  "empresa": "Hyperliquid Strategies",    "mercado": "internacional", "cantidad": 33.27364077, "precio_compra": 6.01,    "precio_actual": 6.02,     "moneda": "USD"},
    {"ticker": "PWR",   "empresa": "Quanta Services",           "mercado": "internacional", "cantidad": 0.16480832,  "precio_compra": 486.14,  "precio_actual": 727.77,   "moneda": "USD"},
    {"ticker": "QQQ",   "empresa": "Invesco QQQ Trust",         "mercado": "internacional", "cantidad": 0.68616911,  "precio_compra": 0.00,    "precio_actual": 667.74,   "moneda": "USD"},
    {"ticker": "QUAL",  "empresa": "iShares MSCI USA Quality",  "mercado": "internacional", "cantidad": 0.43745271,  "precio_compra": 192.02,  "precio_actual": 207.25,   "moneda": "USD"},
    {"ticker": "QUBT",  "empresa": "Quantum Computing",         "mercado": "internacional", "cantidad": 24.96716907, "precio_compra": 16.02,   "precio_actual": 9.02,     "moneda": "USD"},
    {"ticker": "REMX",  "empresa": "VanEck Rare Earth ETF",     "mercado": "internacional", "cantidad": 0.27472214,  "precio_compra": 70.18,   "precio_actual": 105.43,   "moneda": "USD"},
    {"ticker": "RGTI",  "empresa": "Rigetti Computing",         "mercado": "internacional", "cantidad": 10.05002628, "precio_compra": 39.80,   "precio_actual": 17.45,    "moneda": "USD"},
    {"ticker": "RSP",   "empresa": "Invesco S&P500 Equal Wght", "mercado": "internacional", "cantidad": 1.92360591,  "precio_compra": 197.60,  "precio_actual": 203.44,   "moneda": "USD"},
    {"ticker": "SCHH",  "empresa": "Schwab US REIT ETF",        "mercado": "internacional", "cantidad": 47.74179114, "precio_compra": 19.80,   "precio_actual": 23.42,    "moneda": "USD"},
    {"ticker": "SCHP",  "empresa": "Schwab US TIPS ETF",        "mercado": "internacional", "cantidad": 4.2700759,   "precio_compra": 25.03,   "precio_actual": 26.87,    "moneda": "USD"},
    {"ticker": "SGML",  "empresa": "Sigma Lithium",             "mercado": "internacional", "cantidad": 40.48627436, "precio_compra": 0.00,    "precio_actual": 22.07,    "moneda": "USD"},
    {"ticker": "SOFI",  "empresa": "SoFi Technologies",         "mercado": "internacional", "cantidad": 3.70526815,  "precio_compra": 26.99,   "precio_actual": 16.10,    "moneda": "USD"},
    {"ticker": "SQM",   "empresa": "Sociedad Química y Minera", "mercado": "internacional", "cantidad": 113.44991868,"precio_compra": 41.69,   "precio_actual": 92.17,    "moneda": "USD"},
    {"ticker": "TMF",   "empresa": "Direxion 20yr Treasury 3x", "mercado": "internacional", "cantidad": 5.75171447,  "precio_compra": 56.52,   "precio_actual": 34.82,    "moneda": "USD"},
    {"ticker": "TSLA",  "empresa": "Tesla",                     "mercado": "internacional", "cantidad": 1.883617,    "precio_compra": 425.13,  "precio_actual": 381.63,   "moneda": "USD"},
    {"ticker": "TSM",   "empresa": "Taiwan Semiconductor",      "mercado": "internacional", "cantidad": 2.11848957,  "precio_compra": 163.48,  "precio_actual": 396.06,   "moneda": "USD"},
    {"ticker": "UNH",   "empresa": "UnitedHealth Group",        "mercado": "internacional", "cantidad": 8.62844164,  "precio_compra": 297.44,  "precio_actual": 370.48,   "moneda": "USD"},
    {"ticker": "VBR",   "empresa": "Vanguard Small Cap Value",  "mercado": "internacional", "cantidad": 1.14157727,  "precio_compra": 226.00,  "precio_actual": 232.42,   "moneda": "USD"},
    {"ticker": "VCX",   "empresa": "Fundrise Innovation Fund",  "mercado": "internacional", "cantidad": 6.604419,    "precio_compra": 105.99,  "precio_actual": 94.79,    "moneda": "USD"},
    {"ticker": "VEU",   "empresa": "Vanguard All World ex-US",  "mercado": "internacional", "cantidad": 4.67833398,  "precio_compra": 51.14,   "precio_actual": 80.92,    "moneda": "USD"},
    {"ticker": "VGSH",  "empresa": "Vanguard Short Term Treas", "mercado": "internacional", "cantidad": 11.17702752, "precio_compra": 58.87,   "precio_actual": 58.47,    "moneda": "USD"},
    {"ticker": "VNM",   "empresa": "VanEck Vietnam ETF",        "mercado": "internacional", "cantidad": 3.1949426,   "precio_compra": 13.77,   "precio_actual": 18.84,    "moneda": "USD"},
    {"ticker": "VOO",   "empresa": "Vanguard S&P 500 ETF",      "mercado": "internacional", "cantidad": 8.85660244,  "precio_compra": 471.80,  "precio_actual": 660.58,   "moneda": "USD"},
    {"ticker": "VRT",   "empresa": "Vertiv Holdings",           "mercado": "internacional", "cantidad": 0.51220511,  "precio_compra": 212.61,  "precio_actual": 328.49,   "moneda": "USD"},
    {"ticker": "VT",    "empresa": "Vanguard Total World Stock","mercado": "internacional", "cantidad": 34.14496874, "precio_compra": 132.00,  "precio_actual": 151.20,   "moneda": "USD"},
    {"ticker": "VTI",   "empresa": "Vanguard Total Stock Market","mercado": "internacional","cantidad": 8.20658408,  "precio_compra": 263.82,  "precio_actual": 354.18,   "moneda": "USD"},
    {"ticker": "VTIP",  "empresa": "Vanguard Short-Term Inflation","mercado": "internacional","cantidad": 7.42391843,"precio_compra": 50.11,   "precio_actual": 50.36,    "moneda": "USD"},
    {"ticker": "VTV",   "empresa": "Vanguard Value ETF",        "mercado": "internacional", "cantidad": 12.34565141, "precio_compra": 181.40,  "precio_actual": 206.78,   "moneda": "USD"},
    {"ticker": "VWO",   "empresa": "Vanguard FTSE Emg Mkts ETF","mercado": "internacional", "cantidad": 12.44705584, "precio_compra": 52.78,   "precio_actual": 58.93,    "moneda": "USD"},
    {"ticker": "VXUS",  "empresa": "Vanguard Total Intl Stock", "mercado": "internacional", "cantidad": 45.78495025, "precio_compra": 64.53,   "precio_actual": 83.06,    "moneda": "USD"},
    {"ticker": "WMT",   "empresa": "Walmart",                   "mercado": "internacional", "cantidad": 6.5466854,   "precio_compra": 106.97,  "precio_actual": 131.93,   "moneda": "USD"},
    {"ticker": "ZETA",  "empresa": "Zeta Global Holdings",      "mercado": "internacional", "cantidad": 4.12832484,  "precio_compra": 24.22,   "precio_actual": 18.42,    "moneda": "USD"},
]

# Crypto (incluye Buda + cualquier otro hasta 2026-04-30)
CRYPTO = [
    {"ticker": "BTC", "empresa": "Bitcoin",  "mercado": "crypto", "cantidad": 0.058,  "precio_compra": 60000.0, "precio_actual": 76810.0, "moneda": "USD"},
    {"ticker": "ETH", "empresa": "Ethereum", "mercado": "crypto", "cantidad": 1.310,  "precio_compra": 2500.0,  "precio_actual": 3000.0,  "moneda": "USD"},
]


def get_base() -> list[dict]:
    """Retorna lista combinada acciones CL + intl + crypto con fecha_actualizacion."""
    base = []
    for row in ACCIONES_CL + STOCKS_INTL + CRYPTO:
        r = dict(row)
        r["fecha_actualizacion"] = SNAPSHOT_DATE
        base.append(r)
    return base
