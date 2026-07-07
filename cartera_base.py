# ============================================================
# CARTERA BASE — SNAPSHOT INMUTABLE AL 2026-06-30
#
# Fuentes de verdad:
#   - Nacional: Vector Capital Ledger 30/06/2026 (PDF oficial)
#     Patrimonio: $26.510.514 (incl. caja $1.902.078 que NO trackeamos)
#     Renta variable + fondos: $24.608.436
#   - Internacional: DriveWealth Account Statement 30/06/2026 (PDF)
#     Ending Account Value: USD 96,960.46 (equities 96,919.33 + cash 41.13)
#     77 posiciones exactas (8 decimales), account types C+L sumados
#   - Crypto: base 31/05 + compras buda_crypto de junio (22 txs)
#
# update_cartera.py lee de aquí y aplica movimientos posteriores.
# Solo modificar al cierre de mes con nuevas cartolas PDF.
#
# NOTA (2026-07-07): este snapshot ELIMINA la contaminación por
# transacciones duplicadas de junio (email + PDF DriveWealth cargaban
# el mismo trade con montos distintos → AVGO/MRVL/NU/NVDA inflados).
# ============================================================

SNAPSHOT_DATE = "2026-06-30"

# Rentabilidad TWR reportada por Racional al 31/05/2026 (en %).
# TODO: actualizar con el valor que Racional reporte al 30/06.
TWR_PRE_SNAPSHOT_PCT = 46.0

# ── ACCIONES CHILENAS (Vector Capital Ledger al 30/06/2026) ──
# Cantidades y COSTOS del PDF oficial (antes FALABELLA/ITAUCL/CFMITNIPSA
# tenían precio_compra=0; el ledger los trae).
ACCIONES_CL = [
    {"ticker": "BCI",        "empresa": "Banco de Crédito e Inversiones",  "mercado": "nacional", "cantidad": 30.0,     "precio_compra": 23930.43, "precio_actual": 60569.00, "moneda": "CLP"},
    {"ticker": "BSANTANDER", "empresa": "Banco Santander Chile",           "mercado": "nacional", "cantidad": 8916.0,   "precio_compra": 63.16,    "precio_actual": 75.50,    "moneda": "CLP"},
    {"ticker": "CAP",        "empresa": "CAP",                             "mercado": "nacional", "cantidad": 9.0,      "precio_compra": 6631.88,  "precio_actual": 6500.00,  "moneda": "CLP"},
    {"ticker": "CENCOSUD",   "empresa": "Cencosud",                        "mercado": "nacional", "cantidad": 649.0,    "precio_compra": 1970.25,  "precio_actual": 2130.00,  "moneda": "CLP"},
    {"ticker": "CHILE",      "empresa": "Banco de Chile",                  "mercado": "nacional", "cantidad": 3396.0,   "precio_compra": 163.59,   "precio_actual": 180.50,   "moneda": "CLP"},
    {"ticker": "CMPC",       "empresa": "CMPC",                            "mercado": "nacional", "cantidad": 771.0,    "precio_compra": 1397.92,  "precio_actual": 1026.00,  "moneda": "CLP"},
    {"ticker": "COLBUN",     "empresa": "Colbún",                          "mercado": "nacional", "cantidad": 4159.0,   "precio_compra": 147.63,   "precio_actual": 133.00,   "moneda": "CLP"},
    {"ticker": "COPEC",      "empresa": "Empresas Copec",                  "mercado": "nacional", "cantidad": 170.0,    "precio_compra": 6536.42,  "precio_actual": 5751.00,  "moneda": "CLP"},
    {"ticker": "FALABELLA",  "empresa": "Falabella",                       "mercado": "nacional", "cantidad": 1175.0,   "precio_compra": 2680.84,  "precio_actual": 5756.00,  "moneda": "CLP"},
    {"ticker": "IAM",        "empresa": "Inversiones Aguas Metropolitanas","mercado": "nacional", "cantidad": 246.0,    "precio_compra": 941.36,   "precio_actual": 925.10,   "moneda": "CLP"},
    {"ticker": "PARAUCO",    "empresa": "Parque Arauco",                   "mercado": "nacional", "cantidad": 341.0,    "precio_compra": 2977.37,  "precio_actual": 3864.90,  "moneda": "CLP"},
    {"ticker": "QUINENCO",   "empresa": "Quiñenco",                        "mercado": "nacional", "cantidad": 25.0,     "precio_compra": 3366.15,  "precio_actual": 3925.00,  "moneda": "CLP"},
    {"ticker": "ITAUCL",     "empresa": "Banco Itaú Chile",                "mercado": "nacional", "cantidad": 166.0,    "precio_compra": 10099.06, "precio_actual": 18798.00, "moneda": "CLP"},
    {"ticker": "ENELAM",     "empresa": "Enel Américas",                   "mercado": "nacional", "cantidad": 1810.0,   "precio_compra": 87.04,    "precio_actual": 82.60,    "moneda": "CLP"},
    {"ticker": "SMU",        "empresa": "SMU",                             "mercado": "nacional", "cantidad": 228.0,    "precio_compra": 160.85,   "precio_actual": 132.00,   "moneda": "CLP"},
    {"ticker": "LTM",        "empresa": "LATAM Airlines Group",            "mercado": "nacional", "cantidad": 83901.0,  "precio_compra": 19.01,    "precio_actual": 26.81,    "moneda": "CLP"},
    {"ticker": "CFMITNIPSA", "empresa": "ETF Acciones Chilenas Itaú",      "mercado": "nacional", "cantidad": 755.0,    "precio_compra": 3342.96,  "precio_actual": 5014.72,  "moneda": "CLP"},
    # --- Santander Corredora (sufijo _STG, NO están en la cartola Vector) ---
    {"ticker": "ENELCHILE_STG", "empresa": "Enel Chile (Santander)",        "mercado": "nacional", "cantidad": 4800.0,   "precio_compra": 0.0,      "precio_actual": 81.55,    "moneda": "CLP"},
    {"ticker": "ENJOY_STG",     "empresa": "Enjoy S.A. (Santander)",        "mercado": "nacional", "cantidad": 156713.0, "precio_compra": 0.0,      "precio_actual": 0.19,     "moneda": "CLP"},
    {"ticker": "LTM_STG",       "empresa": "LATAM Airlines (Santander)",    "mercado": "nacional", "cantidad": 76820.0,  "precio_compra": 0.0,      "precio_actual": 26.81,    "moneda": "CLP"},
]

# ── STOCKS INTERNACIONALES (DriveWealth al 30/06/2026) ──
# 77 posiciones exactas del statement. Suma: USD 96,919.33 (al centavo).
# Account types C (custody) + L (on loan) sumados por símbolo.
STOCKS_INTL = [
    {"ticker": "AMBA", "empresa": "Ambarella", "mercado": "internacional", "cantidad": 0.08574601, "precio_compra": 93.30, "precio_actual": 85.80, "moneda": "USD"},
    {"ticker": "AMD", "empresa": "Advanced Micro Devices", "mercado": "internacional", "cantidad": 2.64766673, "precio_compra": 202.54, "precio_actual": 580.91, "moneda": "USD"},
    {"ticker": "AMZN", "empresa": "Amazon", "mercado": "internacional", "cantidad": 8.77265634, "precio_compra": 231.41, "precio_actual": 238.34, "moneda": "USD"},
    {"ticker": "ANET", "empresa": "Arista Networks", "mercado": "internacional", "cantidad": 0.95919944, "precio_compra": 141.73, "precio_actual": 169.88, "moneda": "USD"},
    {"ticker": "APO", "empresa": "Apollo Global Management", "mercado": "internacional", "cantidad": 2.66412468, "precio_compra": 112.61, "precio_actual": 118.31, "moneda": "USD"},
    {"ticker": "ARES", "empresa": "Ares Management", "mercado": "internacional", "cantidad": 0.45961468, "precio_compra": 130.54, "precio_actual": 111.31, "moneda": "USD"},
    {"ticker": "ARTY", "empresa": "iShares Future AI & Tech", "mercado": "internacional", "cantidad": 7.40141753, "precio_compra": 0.00, "precio_actual": 76.16, "moneda": "USD"},
    {"ticker": "ASML", "empresa": "ASML Holding", "mercado": "internacional", "cantidad": 1.05788991, "precio_compra": 1379.14, "precio_actual": 1989.44, "moneda": "USD"},
    {"ticker": "ASTS", "empresa": "AST SpaceMobile", "mercado": "internacional", "cantidad": 8.20927508, "precio_compra": 96.24, "precio_actual": 88.86, "moneda": "USD"},
    {"ticker": "AVAV", "empresa": "AeroVironment", "mercado": "internacional", "cantidad": 0.83414211, "precio_compra": 281.35, "precio_actual": 165.07, "moneda": "USD"},
    {"ticker": "AVGO", "empresa": "Broadcom", "mercado": "internacional", "cantidad": 2.35169972, "precio_compra": 389.11, "precio_actual": 377.75, "moneda": "USD"},
    {"ticker": "BE", "empresa": "Bloom Energy", "mercado": "internacional", "cantidad": 4.28061226, "precio_compra": 186.89, "precio_actual": 302.70, "moneda": "USD"},
    {"ticker": "BJ", "empresa": "BJ's Wholesale Club", "mercado": "internacional", "cantidad": 2.04081632, "precio_compra": 98.00, "precio_actual": 87.22, "moneda": "USD"},
    {"ticker": "BND", "empresa": "Vanguard Total Bond Market", "mercado": "internacional", "cantidad": 35.98412489, "precio_compra": 73.26, "precio_actual": 73.41, "moneda": "USD"},
    {"ticker": "CCJ", "empresa": "Cameco Corp", "mercado": "internacional", "cantidad": 6.78983189, "precio_compra": 100.74, "precio_actual": 101.86, "moneda": "USD"},
    {"ticker": "CEG", "empresa": "Constellation Energy", "mercado": "internacional", "cantidad": 2.09211168, "precio_compra": 308.57, "precio_actual": 248.37, "moneda": "USD"},
    {"ticker": "CPER", "empresa": "US Commodity Index Copper", "mercado": "internacional", "cantidad": 21.58332203, "precio_compra": 28.34, "precio_actual": 37.73, "moneda": "USD"},
    {"ticker": "CRWD", "empresa": "CrowdStrike", "mercado": "internacional", "cantidad": 0.52160284, "precio_compra": 384.99, "precio_actual": 763.14, "moneda": "USD"},
    {"ticker": "CRWV", "empresa": "CoreWeave", "mercado": "internacional", "cantidad": 0.36477972, "precio_compra": 109.66, "precio_actual": 99.54, "moneda": "USD"},
    {"ticker": "ESGV", "empresa": "Vanguard ESG US Stock ETF", "mercado": "internacional", "cantidad": 9.22760470, "precio_compra": 79.60, "precio_actual": 132.24, "moneda": "USD"},
    {"ticker": "EWJ", "empresa": "iShares MSCI Japan ETF", "mercado": "internacional", "cantidad": 12.21940612, "precio_compra": 26.47, "precio_actual": 93.27, "moneda": "USD"},
    {"ticker": "EWY", "empresa": "iShares MSCI South Korea", "mercado": "internacional", "cantidad": 7.77046207, "precio_compra": 189.82, "precio_actual": 201.90, "moneda": "USD"},
    {"ticker": "FIG", "empresa": "Figma", "mercado": "internacional", "cantidad": 79.00836846, "precio_compra": 58.00, "precio_actual": 18.09, "moneda": "USD"},
    {"ticker": "FTEC", "empresa": "Fidelity MSCI Info Tech", "mercado": "internacional", "cantidad": 1.76586699, "precio_compra": 131.72, "precio_actual": 285.58, "moneda": "USD"},
    {"ticker": "GLDM", "empresa": "SPDR Gold MiniShares", "mercado": "internacional", "cantidad": 9.44266586, "precio_compra": 79.78, "precio_actual": 79.42, "moneda": "USD"},
    {"ticker": "GOOGL", "empresa": "Alphabet", "mercado": "internacional", "cantidad": 11.44647784, "precio_compra": 157.20, "precio_actual": 357.37, "moneda": "USD"},
    {"ticker": "HOOD", "empresa": "Robinhood", "mercado": "internacional", "cantidad": 3.49040139, "precio_compra": 85.95, "precio_actual": 100.28, "moneda": "USD"},
    {"ticker": "IEF", "empresa": "iShares 7-10yr Treasury", "mercado": "internacional", "cantidad": 17.00471801, "precio_compra": 94.68, "precio_actual": 94.57, "moneda": "USD"},
    {"ticker": "IGF", "empresa": "iShares Global Infra ETF", "mercado": "internacional", "cantidad": 1.37774920, "precio_compra": 60.97, "precio_actual": 66.60, "moneda": "USD"},
    {"ticker": "IJR", "empresa": "iShares Core S&P Small Cap", "mercado": "internacional", "cantidad": 1.89089533, "precio_compra": 105.77, "precio_actual": 148.31, "moneda": "USD"},
    {"ticker": "ILF", "empresa": "iShares Latin America 40", "mercado": "internacional", "cantidad": 0.99191760, "precio_compra": 34.28, "precio_actual": 33.75, "moneda": "USD"},
    {"ticker": "INDA", "empresa": "iShares MSCI India ETF", "mercado": "internacional", "cantidad": 37.21074289, "precio_compra": 49.28, "precio_actual": 49.39, "moneda": "USD"},
    {"ticker": "IONQ", "empresa": "IonQ", "mercado": "internacional", "cantidad": 8.45570252, "precio_compra": 57.95, "precio_actual": 53.26, "moneda": "USD"},
    {"ticker": "IQLT", "empresa": "iShares MSCI Intl Quality", "mercado": "internacional", "cantidad": 23.38699869, "precio_compra": 42.76, "precio_actual": 49.55, "moneda": "USD"},
    {"ticker": "ITUB", "empresa": "Itaú Unibanco", "mercado": "internacional", "cantidad": 59.55167656, "precio_compra": 5.35, "precio_actual": 8.17, "moneda": "USD"},
    {"ticker": "KKR", "empresa": "KKR & Co", "mercado": "internacional", "cantidad": 4.26803546, "precio_compra": 93.72, "precio_actual": 91.78, "moneda": "USD"},
    {"ticker": "LLY", "empresa": "Eli Lilly", "mercado": "internacional", "cantidad": 2.93568611, "precio_compra": 769.66, "precio_actual": 1199.43, "moneda": "USD"},
    {"ticker": "LSCC", "empresa": "Lattice Semiconductor", "mercado": "internacional", "cantidad": 0.17427663, "precio_compra": 59.79, "precio_actual": 152.96, "moneda": "USD"},
    {"ticker": "MELI", "empresa": "MercadoLibre", "mercado": "internacional", "cantidad": 1.29610747, "precio_compra": 1876.67, "precio_actual": 1697.39, "moneda": "USD"},
    {"ticker": "META", "empresa": "Meta Platforms", "mercado": "internacional", "cantidad": 3.17152983, "precio_compra": 533.93, "precio_actual": 563.29, "moneda": "USD"},
    {"ticker": "MP", "empresa": "MP Materials", "mercado": "internacional", "cantidad": 15.59364216, "precio_compra": 64.13, "precio_actual": 56.01, "moneda": "USD"},
    {"ticker": "MRVL", "empresa": "Marvell Technology Group Ltd.", "mercado": "internacional", "cantidad": 2.73164185, "precio_compra": 292.86, "precio_actual": 297.89, "moneda": "USD"},
    {"ticker": "MSFT", "empresa": "Microsoft", "mercado": "internacional", "cantidad": 3.93304809, "precio_compra": 409.86, "precio_actual": 373.02, "moneda": "USD"},
    {"ticker": "MU", "empresa": "Micron Technology", "mercado": "internacional", "cantidad": 1.94776115, "precio_compra": 775.31, "precio_actual": 1154.29, "moneda": "USD"},
    {"ticker": "NBIS", "empresa": "Nebius Group", "mercado": "internacional", "cantidad": 0.17228872, "precio_compra": 232.17, "precio_actual": 276.17, "moneda": "USD"},
    {"ticker": "NU", "empresa": "Nu Holdings", "mercado": "internacional", "cantidad": 356.16406111, "precio_compra": 12.99, "precio_actual": 13.36, "moneda": "USD"},
    {"ticker": "NVDA", "empresa": "Nvidia", "mercado": "internacional", "cantidad": 7.25189377, "precio_compra": 209.61, "precio_actual": 200.09, "moneda": "USD"},
    {"ticker": "NVO", "empresa": "Novo Nordisk", "mercado": "internacional", "cantidad": 7.84447246, "precio_compra": 31.87, "precio_actual": 47.94, "moneda": "USD"},
    {"ticker": "OKLO", "empresa": "Oklo", "mercado": "internacional", "cantidad": 1.46372956, "precio_compra": 61.49, "precio_actual": 52.33, "moneda": "USD"},
    {"ticker": "PANW", "empresa": "Palo Alto Networks", "mercado": "internacional", "cantidad": 0.28645233, "precio_compra": 167.57, "precio_actual": 341.02, "moneda": "USD"},
    {"ticker": "PICK", "empresa": "iShares MSCI Global Metals", "mercado": "internacional", "cantidad": 1.05701068, "precio_compra": 29.40, "precio_actual": 58.15, "moneda": "USD"},
    {"ticker": "PURR", "empresa": "Hyperliquid Strategies", "mercado": "internacional", "cantidad": 33.27364077, "precio_compra": 6.01, "precio_actual": 7.87, "moneda": "USD"},
    {"ticker": "PWR", "empresa": "Quanta Services", "mercado": "internacional", "cantidad": 0.16480832, "precio_compra": 486.14, "precio_actual": 720.04, "moneda": "USD"},
    {"ticker": "QQQ", "empresa": "Invesco QQQ Trust", "mercado": "internacional", "cantidad": 0.68616911, "precio_compra": 0.00, "precio_actual": 736.40, "moneda": "USD"},
    {"ticker": "QUAL", "empresa": "iShares MSCI USA Quality", "mercado": "internacional", "cantidad": 0.43745271, "precio_compra": 192.02, "precio_actual": 219.43, "moneda": "USD"},
    {"ticker": "REMX", "empresa": "VanEck Rare Earth ETF", "mercado": "internacional", "cantidad": 8.92817736, "precio_compra": 106.10, "precio_actual": 88.50, "moneda": "USD"},
    {"ticker": "RSP", "empresa": "Invesco S&P500 Equal Wght", "mercado": "internacional", "cantidad": 1.92360591, "precio_compra": 197.60, "precio_actual": 212.77, "moneda": "USD"},
    {"ticker": "SCHH", "empresa": "Schwab US REIT ETF", "mercado": "internacional", "cantidad": 47.74179114, "precio_compra": 19.80, "precio_actual": 23.68, "moneda": "USD"},
    {"ticker": "SCHP", "empresa": "Schwab US TIPS ETF", "mercado": "internacional", "cantidad": 4.27007590, "precio_compra": 25.03, "precio_actual": 26.50, "moneda": "USD"},
    {"ticker": "SOFI", "empresa": "SoFi Technologies", "mercado": "internacional", "cantidad": 3.70526815, "precio_compra": 26.99, "precio_actual": 17.93, "moneda": "USD"},
    {"ticker": "SQM", "empresa": "Sociedad Química y Minera", "mercado": "internacional", "cantidad": 113.44991868, "precio_compra": 41.69, "precio_actual": 74.04, "moneda": "USD"},
    {"ticker": "TSLA", "empresa": "Tesla", "mercado": "internacional", "cantidad": 1.88361700, "precio_compra": 425.13, "precio_actual": 420.60, "moneda": "USD"},
    {"ticker": "TSM", "empresa": "Taiwan Semiconductor", "mercado": "internacional", "cantidad": 6.15065637, "precio_compra": 320.02, "precio_actual": 477.57, "moneda": "USD"},
    {"ticker": "UNH", "empresa": "UnitedHealth Group", "mercado": "internacional", "cantidad": 8.93219323, "precio_compra": 300.76, "precio_actual": 415.63, "moneda": "USD"},
    {"ticker": "URNM", "empresa": "Sprott Uranium Miners ETF", "mercado": "internacional", "cantidad": 0.19937264, "precio_compra": 60.19, "precio_actual": 52.59, "moneda": "USD"},
    {"ticker": "VBR", "empresa": "Vanguard Small Cap Value", "mercado": "internacional", "cantidad": 1.14157727, "precio_compra": 226.00, "precio_actual": 242.99, "moneda": "USD"},
    {"ticker": "VCX", "empresa": "Fundrise Innovation Fund", "mercado": "internacional", "cantidad": 6.60441900, "precio_compra": 105.99, "precio_actual": 86.43, "moneda": "USD"},
    {"ticker": "VEU", "empresa": "Vanguard All World ex-US", "mercado": "internacional", "cantidad": 4.67833398, "precio_compra": 51.14, "precio_actual": 83.75, "moneda": "USD"},
    {"ticker": "VGSH", "empresa": "Vanguard Short Term Treas", "mercado": "internacional", "cantidad": 11.17702752, "precio_compra": 58.87, "precio_actual": 58.20, "moneda": "USD"},
    {"ticker": "VOO", "empresa": "Vanguard S&P 500 ETF", "mercado": "internacional", "cantidad": 8.89361596, "precio_compra": 472.65, "precio_actual": 686.81, "moneda": "USD"},
    {"ticker": "VRT", "empresa": "Vertiv Holdings", "mercado": "internacional", "cantidad": 0.51220511, "precio_compra": 212.61, "precio_actual": 334.82, "moneda": "USD"},
    {"ticker": "VT", "empresa": "Vanguard Total World Stock", "mercado": "internacional", "cantidad": 34.14496874, "precio_compra": 132.00, "precio_actual": 156.95, "moneda": "USD"},
    {"ticker": "VTI", "empresa": "Vanguard Total Stock Market", "mercado": "internacional", "cantidad": 8.63533793, "precio_compra": 269.01, "precio_actual": 370.04, "moneda": "USD"},
    {"ticker": "VTV", "empresa": "Vanguard Value ETF", "mercado": "internacional", "cantidad": 12.34565141, "precio_compra": 181.40, "precio_actual": 217.93, "moneda": "USD"},
    {"ticker": "VWO", "empresa": "Vanguard FTSE Emg Mkts ETF", "mercado": "internacional", "cantidad": 14.01438739, "precio_compra": 53.52, "precio_actual": 59.69, "moneda": "USD"},
    {"ticker": "VXUS", "empresa": "Vanguard Total Intl Stock", "mercado": "internacional", "cantidad": 49.36227908, "precio_compra": 85.10, "precio_actual": 85.49, "moneda": "USD"},
    {"ticker": "WMT", "empresa": "Walmart", "mercado": "internacional", "cantidad": 6.54668540, "precio_compra": 106.97, "precio_actual": 113.26, "moneda": "USD"},
]

# ── CRYPTO (Buda al 30/06/2026) ──
# Base 31/05 + compras buda_crypto junio (BTC +0.00132681, ETH +0.03958414)
CRYPTO = [
    {"ticker": "BTC", "empresa": "Bitcoin",  "mercado": "crypto", "cantidad": 0.06041681, "precio_compra": 60000.0, "precio_actual": 107000.0, "moneda": "USD"},
    {"ticker": "ETH", "empresa": "Ethereum", "mercado": "crypto", "cantidad": 1.37740414, "precio_compra": 2500.0,  "precio_actual": 2500.0,   "moneda": "USD"},
]


def get_base() -> list[dict]:
    """Retorna lista combinada acciones CL + intl + crypto con fecha_actualizacion."""
    base = []
    for row in ACCIONES_CL + STOCKS_INTL + CRYPTO:
        r = dict(row)
        r["fecha_actualizacion"] = SNAPSHOT_DATE
        base.append(r)
    return base
