# ============================================================
# CARTERA BASE — SNAPSHOT INMUTABLE AL 2026-05-31
#
# Fuentes de verdad:
#   - Nacional: Cartola Vector Capital/Racional 31/05/2026 (PDF)
#     + screenshots app Racional 06/06/2026 (cantidades calculadas)
#   - Internacional: DriveWealth Account Statement 31/05/2026 (PDF)
#     Ending Account Value: USD 94,876.93
#   - Crypto: Calculado desde base anterior + buda_crypto
#
# update_cartera.py lee de aquí y aplica movimientos posteriores.
# Solo modificar cuando se haga un nuevo snapshot mensual.
# ============================================================

SNAPSHOT_DATE = "2026-05-31"

# Rentabilidad TWR reportada por Racional al SNAPSHOT_DATE (en %)
TWR_PRE_SNAPSHOT_PCT = 46.0

# ── ACCIONES CHILENAS (Racional Portafolio CL al 31/05/2026) ──
# Cantidades de 14 stocks: del PDF "Portafolio Acciones Chilenas 31/05/2026"
# ITAUCL, FALABELLA, LTM, CFMITNIPSA: calculadas desde valores app 06/06/2026
# FALABELLA combina dos cuentas (201 + 974 = 1175 acciones)
# Patrimonio total chileno al 31/05: $26.106.863 CLP
ACCIONES_CL = [
    # --- Del PDF (cantidades exactas) ---
    {"ticker": "BCI",        "empresa": "Banco de Crédito e Inversiones",  "mercado": "nacional", "cantidad": 30.0,     "precio_compra": 23930.43,  "precio_actual": 60051.00, "moneda": "CLP"},
    {"ticker": "CENCOSUD",   "empresa": "Cencosud",                        "mercado": "nacional", "cantidad": 649.0,    "precio_compra": 1970.25,   "precio_actual": 2099.00,  "moneda": "CLP"},
    {"ticker": "PARAUCO",    "empresa": "Parque Arauco",                   "mercado": "nacional", "cantidad": 341.0,    "precio_compra": 2977.37,   "precio_actual": 3900.00,  "moneda": "CLP"},
    {"ticker": "COPEC",      "empresa": "Empresas Copec",                  "mercado": "nacional", "cantidad": 170.0,    "precio_compra": 6536.42,   "precio_actual": 6323.40,  "moneda": "CLP"},
    {"ticker": "CMPC",       "empresa": "CMPC",                            "mercado": "nacional", "cantidad": 771.0,    "precio_compra": 1397.92,   "precio_actual": 1066.00,  "moneda": "CLP"},
    {"ticker": "BSANTANDER", "empresa": "Banco Santander Chile",           "mercado": "nacional", "cantidad": 8916.0,   "precio_compra": 63.16,     "precio_actual": 70.00,    "moneda": "CLP"},
    {"ticker": "CHILE",      "empresa": "Banco de Chile",                  "mercado": "nacional", "cantidad": 3396.0,   "precio_compra": 163.59,    "precio_actual": 167.66,   "moneda": "CLP"},
    {"ticker": "COLBUN",     "empresa": "Colbún",                          "mercado": "nacional", "cantidad": 4159.0,   "precio_compra": 147.63,    "precio_actual": 133.60,   "moneda": "CLP"},
    {"ticker": "IAM",        "empresa": "Inversiones Aguas Metropolitanas","mercado": "nacional", "cantidad": 246.0,    "precio_compra": 941.36,    "precio_actual": 955.00,   "moneda": "CLP"},
    {"ticker": "ENELAM",     "empresa": "Enel Américas",                   "mercado": "nacional", "cantidad": 1810.0,   "precio_compra": 87.04,     "precio_actual": 78.00,    "moneda": "CLP"},
    {"ticker": "QUINENCO",   "empresa": "Quiñenco",                        "mercado": "nacional", "cantidad": 25.0,     "precio_compra": 3366.15,   "precio_actual": 3900.00,  "moneda": "CLP"},
    {"ticker": "CAP",        "empresa": "CAP",                             "mercado": "nacional", "cantidad": 9.0,      "precio_compra": 6631.88,   "precio_actual": 6849.00,  "moneda": "CLP"},
    {"ticker": "SMU",        "empresa": "SMU",                             "mercado": "nacional", "cantidad": 228.0,    "precio_compra": 160.85,    "precio_actual": 145.00,   "moneda": "CLP"},
    # --- No en PDF "Mayores Inversiones" (cantidades calculadas) ---
    {"ticker": "LTM",        "empresa": "LATAM Airlines Group",            "mercado": "nacional", "cantidad": 83901.0,  "precio_compra": 19.01,     "precio_actual": 22.12,    "moneda": "CLP"},
    {"ticker": "ITAUCL",     "empresa": "Banco Itaú Chile",                "mercado": "nacional", "cantidad": 166.0,    "precio_compra": 0.0,       "precio_actual": 17700.00, "moneda": "CLP"},
    {"ticker": "FALABELLA",  "empresa": "Falabella",                       "mercado": "nacional", "cantidad": 1175.0,   "precio_compra": 0.0,       "precio_actual": 5511.00,  "moneda": "CLP"},
    {"ticker": "CFMITNIPSA", "empresa": "ETF Acciones Chilenas Itaú",      "mercado": "nacional", "cantidad": 755.0,    "precio_compra": 0.0,       "precio_actual": 4779.20,  "moneda": "CLP"},
    # --- Santander Corredora (sufijo _STG) ---
    {"ticker": "ENELCHILE_STG", "empresa": "Enel Chile (Santander)",        "mercado": "nacional", "cantidad": 4800.0,   "precio_compra": 0.0,       "precio_actual": 81.55,    "moneda": "CLP"},
    {"ticker": "ENJOY_STG",     "empresa": "Enjoy S.A. (Santander)",        "mercado": "nacional", "cantidad": 156713.0, "precio_compra": 0.0,       "precio_actual": 0.19,     "moneda": "CLP"},
    {"ticker": "LTM_STG",       "empresa": "LATAM Airlines (Santander)",    "mercado": "nacional", "cantidad": 76820.0,  "precio_compra": 0.0,       "precio_actual": 22.12,    "moneda": "CLP"},
]

# ── STOCKS INTERNACIONALES (DriveWealth al 31/05/2026) ──
# Fuente: PDF "Account Statement May 01-31, 2026"
# Ending Account Value: $94,876.93 (Equities $94,241.42 + Cash $635.51)
# Cantidades EXACTAS del PDF (8 decimales)
# BE y VCX combinan account types C + L
STOCKS_INTL = [
    {"ticker": "AMBA",  "empresa": "Ambarella",                  "mercado": "internacional", "cantidad": 0.08574601,   "precio_compra": 93.30,    "precio_actual": 72.18,    "moneda": "USD"},
    {"ticker": "AMD",   "empresa": "Advanced Micro Devices",     "mercado": "internacional", "cantidad": 2.64766673,   "precio_compra": 202.54,   "precio_actual": 516.10,   "moneda": "USD"},
    {"ticker": "AMZN",  "empresa": "Amazon",                     "mercado": "internacional", "cantidad": 8.60856196,   "precio_compra": 231.18,   "precio_actual": 270.64,   "moneda": "USD"},
    {"ticker": "ANET",  "empresa": "Arista Networks",            "mercado": "internacional", "cantidad": 0.95919944,   "precio_compra": 141.73,   "precio_actual": 159.47,   "moneda": "USD"},
    {"ticker": "APO",   "empresa": "Apollo Global Management",   "mercado": "internacional", "cantidad": 2.66412468,   "precio_compra": 112.61,   "precio_actual": 128.71,   "moneda": "USD"},
    {"ticker": "ARES",  "empresa": "Ares Management",            "mercado": "internacional", "cantidad": 0.11770355,   "precio_compra": 127.44,   "precio_actual": 128.50,   "moneda": "USD"},
    {"ticker": "ARTY",  "empresa": "iShares Future AI & Tech",   "mercado": "internacional", "cantidad": 7.40141753,   "precio_compra": 0.00,     "precio_actual": 74.66,    "moneda": "USD"},
    {"ticker": "ASML",  "empresa": "ASML Holding",               "mercado": "internacional", "cantidad": 1.03431772,   "precio_compra": 1369.97,  "precio_actual": 1612.76,  "moneda": "USD"},
    {"ticker": "ASTS",  "empresa": "AST SpaceMobile",            "mercado": "internacional", "cantidad": 8.20927508,   "precio_compra": 96.24,    "precio_actual": 113.41,   "moneda": "USD"},
    {"ticker": "AVAV",  "empresa": "AeroVironment",              "mercado": "internacional", "cantidad": 0.83414211,   "precio_compra": 281.35,   "precio_actual": 207.24,   "moneda": "USD"},
    {"ticker": "AVGO",  "empresa": "Broadcom",                   "mercado": "internacional", "cantidad": 0.32239524,   "precio_compra": 356.92,   "precio_actual": 446.77,   "moneda": "USD"},
    {"ticker": "BE",    "empresa": "Bloom Energy",               "mercado": "internacional", "cantidad": 4.28061226,   "precio_compra": 186.89,   "precio_actual": 285.00,   "moneda": "USD"},
    {"ticker": "BJ",    "empresa": "BJ's Wholesale Club",        "mercado": "internacional", "cantidad": 2.04081632,   "precio_compra": 98.00,    "precio_actual": 85.28,    "moneda": "USD"},
    {"ticker": "BND",   "empresa": "Vanguard Total Bond Market", "mercado": "internacional", "cantidad": 35.98412489,  "precio_compra": 73.26,    "precio_actual": 73.46,    "moneda": "USD"},
    {"ticker": "CCJ",   "empresa": "Cameco Corp",                "mercado": "internacional", "cantidad": 6.57314768,   "precio_compra": 100.41,   "precio_actual": 112.70,   "moneda": "USD"},
    {"ticker": "CEG",   "empresa": "Constellation Energy",       "mercado": "internacional", "cantidad": 2.09211168,   "precio_compra": 308.57,   "precio_actual": 287.75,   "moneda": "USD"},
    {"ticker": "CPER",  "empresa": "US Commodity Index Copper",  "mercado": "internacional", "cantidad": 21.58332203,  "precio_compra": 28.34,    "precio_actual": 38.86,    "moneda": "USD"},
    {"ticker": "CRWD",  "empresa": "CrowdStrike",                "mercado": "internacional", "cantidad": 0.52160284,   "precio_compra": 384.99,   "precio_actual": 731.00,   "moneda": "USD"},
    {"ticker": "CRWV",  "empresa": "CoreWeave",                  "mercado": "internacional", "cantidad": 0.15520921,   "precio_compra": 103.09,   "precio_actual": 109.53,   "moneda": "USD"},
    {"ticker": "ESGV",  "empresa": "Vanguard ESG US Stock ETF",  "mercado": "internacional", "cantidad": 9.2276047,    "precio_compra": 79.60,    "precio_actual": 134.05,   "moneda": "USD"},
    {"ticker": "EWJ",   "empresa": "iShares MSCI Japan ETF",     "mercado": "internacional", "cantidad": 12.21940612,  "precio_compra": 26.47,    "precio_actual": 92.96,    "moneda": "USD"},
    {"ticker": "EWY",   "empresa": "iShares MSCI South Korea",   "mercado": "internacional", "cantidad": 5.48067801,   "precio_compra": 187.93,   "precio_actual": 205.83,   "moneda": "USD"},
    {"ticker": "FIG",   "empresa": "Figma",                      "mercado": "internacional", "cantidad": 79.00836846,  "precio_compra": 58.00,    "precio_actual": 25.50,    "moneda": "USD"},
    {"ticker": "FTEC",  "empresa": "Fidelity MSCI Info Tech",    "mercado": "internacional", "cantidad": 1.76586699,   "precio_compra": 131.72,   "precio_actual": 289.25,   "moneda": "USD"},
    {"ticker": "GLDM",  "empresa": "SPDR Gold MiniShares",       "mercado": "internacional", "cantidad": 8.7362991,    "precio_compra": 79.37,    "precio_actual": 89.93,    "moneda": "USD"},
    {"ticker": "GOOGL", "empresa": "Alphabet",                   "mercado": "internacional", "cantidad": 11.30770263,  "precio_compra": 154.71,   "precio_actual": 380.34,   "moneda": "USD"},
    {"ticker": "IEF",   "empresa": "iShares 7-10yr Treasury",    "mercado": "internacional", "cantidad": 17.00471801,  "precio_compra": 94.68,    "precio_actual": 94.65,    "moneda": "USD"},
    {"ticker": "IGF",   "empresa": "iShares Global Infra ETF",   "mercado": "internacional", "cantidad": 1.3777492,    "precio_compra": 60.97,    "precio_actual": 66.60,    "moneda": "USD"},
    {"ticker": "IJR",   "empresa": "iShares Core S&P Small Cap", "mercado": "internacional", "cantidad": 1.89089533,   "precio_compra": 105.77,   "precio_actual": 138.66,   "moneda": "USD"},
    {"ticker": "ILF",   "empresa": "iShares Latin America 40",   "mercado": "internacional", "cantidad": 0.29096156,   "precio_compra": 34.37,    "precio_actual": 34.94,    "moneda": "USD"},
    {"ticker": "INDA",  "empresa": "iShares MSCI India ETF",     "mercado": "internacional", "cantidad": 36.1420955,   "precio_compra": 49.70,    "precio_actual": 48.56,    "moneda": "USD"},
    {"ticker": "IONQ",  "empresa": "IonQ",                       "mercado": "internacional", "cantidad": 7.79991604,   "precio_compra": 57.69,    "precio_actual": 72.07,    "moneda": "USD"},
    {"ticker": "IQLT",  "empresa": "iShares MSCI Intl Quality",  "mercado": "internacional", "cantidad": 23.38699869,  "precio_compra": 42.76,    "precio_actual": 49.37,    "moneda": "USD"},
    {"ticker": "ITUB",  "empresa": "Itaú Unibanco",              "mercado": "internacional", "cantidad": 59.55167656,  "precio_compra": 5.35,     "precio_actual": 7.88,     "moneda": "USD"},
    {"ticker": "KKR",   "empresa": "KKR & Co",                   "mercado": "internacional", "cantidad": 4.26803546,   "precio_compra": 93.72,    "precio_actual": 95.94,    "moneda": "USD"},
    {"ticker": "LSCC",  "empresa": "Lattice Semiconductor",      "mercado": "internacional", "cantidad": 0.17427663,   "precio_compra": 59.79,    "precio_actual": 147.08,   "moneda": "USD"},
    {"ticker": "LLY",   "empresa": "Eli Lilly",                  "mercado": "internacional", "cantidad": 2.88985476,   "precio_compra": 763.88,   "precio_actual": 1105.00,  "moneda": "USD"},
    {"ticker": "MELI",  "empresa": "MercadoLibre",               "mercado": "internacional", "cantidad": 1.22059513,   "precio_compra": 1890.36,  "precio_actual": 1695.65,  "moneda": "USD"},
    {"ticker": "META",  "empresa": "Meta Platforms",              "mercado": "internacional", "cantidad": 3.17152983,   "precio_compra": 533.93,   "precio_actual": 632.51,   "moneda": "USD"},
    {"ticker": "MP",    "empresa": "MP Materials",                "mercado": "internacional", "cantidad": 15.59364216,  "precio_compra": 64.13,    "precio_actual": 64.70,    "moneda": "USD"},
    {"ticker": "MSFT",  "empresa": "Microsoft",                  "mercado": "internacional", "cantidad": 3.83933653,   "precio_compra": 409.71,   "precio_actual": 450.24,   "moneda": "USD"},
    {"ticker": "MU",    "empresa": "Micron Technology",           "mercado": "internacional", "cantidad": 1.21440068,   "precio_compra": 666.74,   "precio_actual": 971.00,   "moneda": "USD"},
    {"ticker": "NBIS",  "empresa": "Nebius Group",                "mercado": "internacional", "cantidad": 0.07944617,   "precio_compra": 201.39,   "precio_actual": 231.09,   "moneda": "USD"},
    {"ticker": "NU",    "empresa": "Nu Holdings",                 "mercado": "internacional", "cantidad": 343.26131441, "precio_compra": 13.02,    "precio_actual": 13.13,    "moneda": "USD"},
    {"ticker": "NVDA",  "empresa": "Nvidia",                      "mercado": "internacional", "cantidad": 2.10834142,   "precio_compra": 211.11,   "precio_actual": 211.14,   "moneda": "USD"},
    {"ticker": "NVO",   "empresa": "Novo Nordisk",                "mercado": "internacional", "cantidad": 7.84447246,   "precio_compra": 31.87,    "precio_actual": 45.58,    "moneda": "USD"},
    {"ticker": "OKLO",  "empresa": "Oklo",                        "mercado": "internacional", "cantidad": 0.25663398,   "precio_compra": 70.14,    "precio_actual": 66.88,    "moneda": "USD"},
    {"ticker": "PANW",  "empresa": "Palo Alto Networks",          "mercado": "internacional", "cantidad": 0.28645233,   "precio_compra": 167.57,   "precio_actual": 281.69,   "moneda": "USD"},
    {"ticker": "PICK",  "empresa": "iShares MSCI Global Metals",  "mercado": "internacional", "cantidad": 1.05701068,   "precio_compra": 29.40,    "precio_actual": 66.09,    "moneda": "USD"},
    {"ticker": "PURR",  "empresa": "Hyperliquid Strategies",      "mercado": "internacional", "cantidad": 33.27364077,  "precio_compra": 6.01,     "precio_actual": 9.99,     "moneda": "USD"},
    {"ticker": "PWR",   "empresa": "Quanta Services",             "mercado": "internacional", "cantidad": 0.16480832,   "precio_compra": 486.14,   "precio_actual": 711.73,   "moneda": "USD"},
    {"ticker": "QQQ",   "empresa": "Invesco QQQ Trust",           "mercado": "internacional", "cantidad": 0.68616911,   "precio_compra": 0.00,     "precio_actual": 738.31,   "moneda": "USD"},
    {"ticker": "QUAL",  "empresa": "iShares MSCI USA Quality",    "mercado": "internacional", "cantidad": 0.43745271,   "precio_compra": 192.02,   "precio_actual": 215.49,   "moneda": "USD"},
    {"ticker": "REMX",  "empresa": "VanEck Rare Earth ETF",       "mercado": "internacional", "cantidad": 8.92817736,   "precio_compra": 106.10,   "precio_actual": 99.63,    "moneda": "USD"},
    {"ticker": "RSP",   "empresa": "Invesco S&P500 Equal Wght",   "mercado": "internacional", "cantidad": 1.92360591,   "precio_compra": 197.60,   "precio_actual": 208.83,   "moneda": "USD"},
    {"ticker": "SCHH",  "empresa": "Schwab US REIT ETF",          "mercado": "internacional", "cantidad": 47.74179114,  "precio_compra": 19.80,    "precio_actual": 23.45,    "moneda": "USD"},
    {"ticker": "SCHP",  "empresa": "Schwab US TIPS ETF",          "mercado": "internacional", "cantidad": 4.2700759,    "precio_compra": 25.03,    "precio_actual": 26.83,    "moneda": "USD"},
    {"ticker": "SOFI",  "empresa": "SoFi Technologies",           "mercado": "internacional", "cantidad": 3.70526815,   "precio_compra": 26.99,    "precio_actual": 18.22,    "moneda": "USD"},
    {"ticker": "SQM",   "empresa": "Sociedad Química y Minera",   "mercado": "internacional", "cantidad": 113.44991868, "precio_compra": 41.69,    "precio_actual": 85.87,    "moneda": "USD"},
    {"ticker": "TSLA",  "empresa": "Tesla",                       "mercado": "internacional", "cantidad": 1.883617,     "precio_compra": 425.13,   "precio_actual": 435.79,   "moneda": "USD"},
    {"ticker": "TSM",   "empresa": "Taiwan Semiconductor",        "mercado": "internacional", "cantidad": 5.94820732,   "precio_compra": 315.78,   "precio_actual": 418.45,   "moneda": "USD"},
    {"ticker": "UNH",   "empresa": "UnitedHealth Group",          "mercado": "internacional", "cantidad": 8.73223661,   "precio_compra": 298.49,   "precio_actual": 380.31,   "moneda": "USD"},
    {"ticker": "URNM",  "empresa": "Sprott Uranium Miners ETF",   "mercado": "internacional", "cantidad": 0.19937264,   "precio_compra": 60.19,    "precio_actual": 61.28,    "moneda": "USD"},
    {"ticker": "VBR",   "empresa": "Vanguard Small Cap Value",    "mercado": "internacional", "cantidad": 1.14157727,   "precio_compra": 226.00,   "precio_actual": 234.83,   "moneda": "USD"},
    {"ticker": "VCX",   "empresa": "Fundrise Innovation Fund",    "mercado": "internacional", "cantidad": 6.604419,     "precio_compra": 105.99,   "precio_actual": 211.00,   "moneda": "USD"},
    {"ticker": "VEU",   "empresa": "Vanguard All World ex-US",    "mercado": "internacional", "cantidad": 4.67833398,   "precio_compra": 51.14,    "precio_actual": 84.00,    "moneda": "USD"},
    {"ticker": "VGSH",  "empresa": "Vanguard Short Term Treas",   "mercado": "internacional", "cantidad": 11.17702752,  "precio_compra": 58.87,    "precio_actual": 58.35,    "moneda": "USD"},
    {"ticker": "VOO",   "empresa": "Vanguard S&P 500 ETF",        "mercado": "internacional", "cantidad": 8.89361596,   "precio_compra": 472.65,   "precio_actual": 695.49,   "moneda": "USD"},
    {"ticker": "VRT",   "empresa": "Vertiv Holdings",              "mercado": "internacional", "cantidad": 0.51220511,   "precio_compra": 212.61,   "precio_actual": 315.71,   "moneda": "USD"},
    {"ticker": "VT",    "empresa": "Vanguard Total World Stock",   "mercado": "internacional", "cantidad": 34.14496874,  "precio_compra": 132.00,   "precio_actual": 158.12,   "moneda": "USD"},
    {"ticker": "VTI",   "empresa": "Vanguard Total Stock Market",  "mercado": "internacional", "cantidad": 8.39288472,   "precio_compra": 266.06,   "precio_actual": 372.54,   "moneda": "USD"},
    {"ticker": "VTV",   "empresa": "Vanguard Value ETF",           "mercado": "internacional", "cantidad": 12.34565141,  "precio_compra": 181.40,   "precio_actual": 211.85,   "moneda": "USD"},
    {"ticker": "VWO",   "empresa": "Vanguard FTSE Emg Mkts ETF",  "mercado": "internacional", "cantidad": 13.26707013,  "precio_compra": 53.14,    "precio_actual": 59.88,    "moneda": "USD"},
    {"ticker": "VXUS",  "empresa": "Vanguard Total Intl Stock",    "mercado": "internacional", "cantidad": 46.73753604,  "precio_compra": 64.93,    "precio_actual": 86.06,    "moneda": "USD"},
    {"ticker": "WMT",   "empresa": "Walmart",                     "mercado": "internacional", "cantidad": 6.5466854,    "precio_compra": 106.97,   "precio_actual": 115.75,   "moneda": "USD"},
]

# ── CRYPTO (Buda, calculado al 31/05/2026) ──
# Base anterior (0.058 BTC, 1.310 ETH al 30/04) + compras buda mayo
# TODO: Verificar con saldos reales de Buda
CRYPTO = [
    {"ticker": "BTC", "empresa": "Bitcoin",  "mercado": "crypto", "cantidad": 0.05909,  "precio_compra": 60000.0, "precio_actual": 108000.0, "moneda": "USD"},
    {"ticker": "ETH", "empresa": "Ethereum", "mercado": "crypto", "cantidad": 1.33782,  "precio_compra": 2500.0,  "precio_actual": 2550.0,   "moneda": "USD"},
]


def get_base() -> list[dict]:
    """Retorna lista combinada acciones CL + intl + crypto con fecha_actualizacion."""
    base = []
    for row in ACCIONES_CL + STOCKS_INTL + CRYPTO:
        r = dict(row)
        r["fecha_actualizacion"] = SNAPSHOT_DATE
        base.append(r)
    return base
