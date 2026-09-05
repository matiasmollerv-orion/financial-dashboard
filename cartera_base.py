# ============================================================
# CARTERA BASE — SNAPSHOT INMUTABLE AL 2026-08-31
#
# Fuentes de verdad:
#   - Nacional: Vector Capital Ledger 31/08/2026 (PDF oficial)
#     Patrimonio Actual: $27.755.186
#     Renta variable + fondos: $25.893.149 (Acciones $21.940.724 + CFMITNIPSA $3.952.425)
#     Caja: $1.862.037 (AHORA SÍ trackeada, ver ticker CAJA_CLP)
#   - Internacional: DriveWealth Account Statement 31/08/2026 (PDF)
#     Ending Account Value: USD 97,500.10 (68 posiciones + cash sweep DWBDS 44.27)
#   - Crypto: sin cambios desde snapshot anterior (update_cartera.py aplica
#     buda_crypto normalmente, no requiere refresh de cartola oficial)
#
# update_cartera.py lee de aquí y aplica movimientos posteriores.
# Solo modificar al cierre de mes con nuevas cartolas PDF.
#
# NOTA (2026-09-04): reconciliación real vs. lo que el sistema calculaba
# encontró 3 gaps reales:
#   1. Caja nacional nunca se trackeaba (gap $1.862.037, 68% del error) —
#      agregado ticker CAJA_CLP. Mismo problema del lado internacional
#      (cash sweep DWBDS, ~USD 44) — agregado también.
#   2. Precios yfinance (.SN) para acciones chilenas divergen de la
#      valorización real del corredor (gap $684.510, 25%) — ej. ITAUCL
#      $20.678 (yfinance) vs $22.100 (Vector real). Limitación de fuente
#      de datos, no bug — por eso este snapshot mensual importa tanto acá.
#   3. CFMITNIPSA (fondo mutuo, sin cotización en yfinance) con precio de
#      2 meses atrás (gap $166.311, 6%).
#   Del lado internacional: 2 duplicados email+PDF nuevos (NU 25/08, FTEC
#   24/08) que el fix de load_racional_pdf.py NO cubría — solo protegía
#   cuando el PDF llega después del correo, no al revés. CRWD sigue sin
#   resolverse limpio (viejo misterio de los $423, no es duplicado simple).
#   Este snapshot nuevo hace irrelevante esa contaminación histórica hacia
#   adelante — por eso el refresh mensual es la defensa real, más que
#   perseguir cada duplicado en el historial.
# ============================================================

SNAPSHOT_DATE = "2026-08-31"

# Rentabilidad TWR reportada por Racional (en %, desde inicio de cuenta).
# TODO: NO actualizado en este snapshot — no se pidió el dato a Matías,
# no inventar un número. Sigue el valor de mayo, probablemente stale.
TWR_PRE_SNAPSHOT_PCT = 46.0

# ── ACCIONES CHILENAS (Vector Capital Ledger al 31/08/2026) ──
ACCIONES_CL = [
    {"ticker": "BCI",        "empresa": "Banco de Crédito e Inversiones",  "mercado": "nacional", "cantidad": 30.0,     "precio_compra": 23930.43, "precio_actual": 64500.00, "moneda": "CLP"},
    {"ticker": "BSANTANDER", "empresa": "Banco Santander Chile",           "mercado": "nacional", "cantidad": 8916.0,   "precio_compra": 63.16,    "precio_actual": 80.51,    "moneda": "CLP"},
    {"ticker": "CAP",        "empresa": "CAP",                             "mercado": "nacional", "cantidad": 9.0,      "precio_compra": 6631.88,  "precio_actual": 5550.00,  "moneda": "CLP"},
    {"ticker": "CENCOSUD",   "empresa": "Cencosud",                        "mercado": "nacional", "cantidad": 649.0,    "precio_compra": 1970.25,  "precio_actual": 1956.00,  "moneda": "CLP"},
    {"ticker": "CHILE",      "empresa": "Banco de Chile",                  "mercado": "nacional", "cantidad": 3396.0,   "precio_compra": 163.59,   "precio_actual": 192.50,   "moneda": "CLP"},
    {"ticker": "CMPC",       "empresa": "CMPC",                            "mercado": "nacional", "cantidad": 771.0,    "precio_compra": 1397.92,  "precio_actual": 1005.00,  "moneda": "CLP"},
    {"ticker": "COLBUN",     "empresa": "Colbún",                          "mercado": "nacional", "cantidad": 4159.0,   "precio_compra": 147.63,   "precio_actual": 147.50,   "moneda": "CLP"},
    {"ticker": "COPEC",      "empresa": "Empresas Copec",                  "mercado": "nacional", "cantidad": 170.0,    "precio_compra": 6536.42,  "precio_actual": 6620.00,  "moneda": "CLP"},
    {"ticker": "FALABELLA",  "empresa": "Falabella",                       "mercado": "nacional", "cantidad": 1175.0,   "precio_compra": 2680.84,  "precio_actual": 6180.00,  "moneda": "CLP"},
    {"ticker": "IAM",        "empresa": "Inversiones Aguas Metropolitanas","mercado": "nacional", "cantidad": 246.0,    "precio_compra": 941.36,   "precio_actual": 905.00,   "moneda": "CLP"},
    {"ticker": "PARAUCO",    "empresa": "Parque Arauco",                   "mercado": "nacional", "cantidad": 341.0,    "precio_compra": 2977.37,  "precio_actual": 3900.00,  "moneda": "CLP"},
    {"ticker": "QUINENCO",   "empresa": "Quiñenco",                        "mercado": "nacional", "cantidad": 25.0,     "precio_compra": 3366.15,  "precio_actual": 4500.00,  "moneda": "CLP"},
    {"ticker": "ITAUCL",     "empresa": "Banco Itaú Chile",                "mercado": "nacional", "cantidad": 166.0,    "precio_compra": 10099.06, "precio_actual": 22100.00, "moneda": "CLP"},
    {"ticker": "ENELAM",     "empresa": "Enel Américas",                   "mercado": "nacional", "cantidad": 1810.0,   "precio_compra": 87.04,    "precio_actual": 84.50,    "moneda": "CLP"},
    {"ticker": "SMU",        "empresa": "SMU",                             "mercado": "nacional", "cantidad": 228.0,    "precio_compra": 160.85,   "precio_actual": 128.50,   "moneda": "CLP"},
    {"ticker": "LTM",        "empresa": "LATAM Airlines Group",            "mercado": "nacional", "cantidad": 83901.0,  "precio_compra": 19.01,    "precio_actual": 24.12,    "moneda": "CLP"},
    {"ticker": "CFMITNIPSA", "empresa": "ETF Acciones Chilenas Itaú",      "mercado": "nacional", "cantidad": 755.0,    "precio_compra": 3342.96,  "precio_actual": 5235.00,  "moneda": "CLP"},
    # Caja no invertida del portafolio Racional nacional (dividendos, etc.)
    # Modelada como 1 "unidad" a precio = monto total, para no inventar
    # cantidad/precio artificiales. Ver mappings.py (tipo=Efectivo).
    {"ticker": "CAJA_CLP",   "empresa": "Caja Racional (no invertida)",    "mercado": "nacional", "cantidad": 1.0,      "precio_compra": 1862037.0, "precio_actual": 1862037.0, "moneda": "CLP"},
    # --- Santander Corredora (sufijo _STG, NO están en la cartola Vector) ---
    {"ticker": "ENELCHILE_STG", "empresa": "Enel Chile (Santander)",        "mercado": "nacional", "cantidad": 4800.0,   "precio_compra": 0.0,      "precio_actual": 81.55,    "moneda": "CLP"},
    {"ticker": "ENJOY_STG",     "empresa": "Enjoy S.A. (Santander)",        "mercado": "nacional", "cantidad": 156713.0, "precio_compra": 0.0,      "precio_actual": 0.19,     "moneda": "CLP"},
    {"ticker": "LTM_STG",       "empresa": "LATAM Airlines (Santander)",    "mercado": "nacional", "cantidad": 76820.0,  "precio_compra": 0.0,      "precio_actual": 24.12,    "moneda": "CLP"},
]

# ── STOCKS INTERNACIONALES (DriveWealth al 31/08/2026) ──
# 69 posiciones exactas del statement (incl. cash sweep DWBDS). Suma: USD 97,500.10 (al centavo).
STOCKS_INTL = [
    {"ticker": "AMD", "empresa": "Advanced Micro Devices", "mercado": "internacional", "cantidad": 2.64766673, "precio_compra": 202.54, "precio_actual": 470.72, "moneda": "USD"},
    {"ticker": "AMZN", "empresa": "Amazon", "mercado": "internacional", "cantidad": 8.97334905, "precio_compra": 231.81, "precio_actual": 259.77, "moneda": "USD"},
    {"ticker": "ANET", "empresa": "Arista Networks", "mercado": "internacional", "cantidad": 0.95919944, "precio_compra": 141.73, "precio_actual": 195.69, "moneda": "USD"},
    {"ticker": "ARES", "empresa": "Ares Management", "mercado": "internacional", "cantidad": 0.91603742, "precio_compra": 131.00, "precio_actual": 143.17, "moneda": "USD"},
    {"ticker": "ARTY", "empresa": "iShares Future AI & Tech", "mercado": "internacional", "cantidad": 7.40141753, "precio_compra": 0.00, "precio_actual": 74.43, "moneda": "USD"},
    {"ticker": "ASML", "empresa": "ASML Holding", "mercado": "internacional", "cantidad": 1.10641131, "precio_compra": 1394.58, "precio_actual": 1696.01, "moneda": "USD"},
    {"ticker": "ASTS", "empresa": "AST SpaceMobile", "mercado": "internacional", "cantidad": 8.20927508, "precio_compra": 96.24, "precio_actual": 59.10, "moneda": "USD"},
    {"ticker": "AVGO", "empresa": "Broadcom", "mercado": "internacional", "cantidad": 2.35169972, "precio_compra": 389.11, "precio_actual": 370.34, "moneda": "USD"},
    {"ticker": "BE", "empresa": "Bloom Energy", "mercado": "internacional", "cantidad": 4.28061226, "precio_compra": 186.89, "precio_actual": 206.30, "moneda": "USD"},
    {"ticker": "BND", "empresa": "Vanguard Total Bond Market", "mercado": "internacional", "cantidad": 35.98412489, "precio_compra": 73.26, "precio_actual": 72.24, "moneda": "USD"},
    {"ticker": "CBRS", "empresa": "Cerebras Systems", "mercado": "internacional", "cantidad": 5.30688364, "precio_compra": 179.01, "precio_actual": 184.24, "moneda": "USD"},
    {"ticker": "CCJ", "empresa": "Cameco Corp", "mercado": "internacional", "cantidad": 7.05128867, "precio_compra": 100.41, "precio_actual": 98.76, "moneda": "USD"},
    {"ticker": "CEG", "empresa": "Constellation Energy", "mercado": "internacional", "cantidad": 2.09211168, "precio_compra": 308.57, "precio_actual": 274.77, "moneda": "USD"},
    {"ticker": "CPER", "empresa": "US Commodity Index Copper", "mercado": "internacional", "cantidad": 21.58332203, "precio_compra": 28.34, "precio_actual": 40.00, "moneda": "USD"},
    {"ticker": "CRWV", "empresa": "CoreWeave", "mercado": "internacional", "cantidad": 0.76771209, "precio_compra": 93.79, "precio_actual": 84.89, "moneda": "USD"},
    {"ticker": "EWJ", "empresa": "iShares MSCI Japan ETF", "mercado": "internacional", "cantidad": 12.21940612, "precio_compra": 26.47, "precio_actual": 95.88, "moneda": "USD"},
    {"ticker": "EWY", "empresa": "iShares MSCI South Korea", "mercado": "internacional", "cantidad": 8.21843180, "precio_compra": 188.60, "precio_actual": 180.86, "moneda": "USD"},
    {"ticker": "FIG", "empresa": "Figma", "mercado": "internacional", "cantidad": 79.00836846, "precio_compra": 58.00, "precio_actual": 27.49, "moneda": "USD"},
    {"ticker": "GLDM", "empresa": "SPDR Gold MiniShares", "mercado": "internacional", "cantidad": 9.98232550, "precio_compra": 79.98, "precio_actual": 88.11, "moneda": "USD"},
    {"ticker": "GOOGL", "empresa": "Alphabet", "mercado": "internacional", "cantidad": 11.53448269, "precio_compra": 158.60, "precio_actual": 339.35, "moneda": "USD"},
    {"ticker": "IEF", "empresa": "iShares 7-10yr Treasury", "mercado": "internacional", "cantidad": 17.00471801, "precio_compra": 94.68, "precio_actual": 92.74, "moneda": "USD"},
    {"ticker": "IGF", "empresa": "iShares Global Infra ETF", "mercado": "internacional", "cantidad": 1.37774920, "precio_compra": 60.97, "precio_actual": 65.14, "moneda": "USD"},
    {"ticker": "IJR", "empresa": "iShares Core S&P Small Cap", "mercado": "internacional", "cantidad": 1.89089533, "precio_compra": 105.77, "precio_actual": 144.52, "moneda": "USD"},
    {"ticker": "ILF", "empresa": "iShares Latin America 40", "mercado": "internacional", "cantidad": 1.68606767, "precio_compra": 34.40, "precio_actual": 34.90, "moneda": "USD"},
    {"ticker": "INDA", "empresa": "iShares MSCI India ETF", "mercado": "internacional", "cantidad": 38.52662122, "precio_compra": 49.66, "precio_actual": 49.70, "moneda": "USD"},
    {"ticker": "IONQ", "empresa": "IonQ", "mercado": "internacional", "cantidad": 17.97559639, "precio_compra": 46.17, "precio_actual": 39.31, "moneda": "USD"},
    {"ticker": "ITUB", "empresa": "Itaú Unibanco", "mercado": "internacional", "cantidad": 59.55167656, "precio_compra": 5.35, "precio_actual": 7.61, "moneda": "USD"},
    {"ticker": "KKR", "empresa": "KKR & Co", "mercado": "internacional", "cantidad": 4.26803546, "precio_compra": 93.72, "precio_actual": 109.72, "moneda": "USD"},
    {"ticker": "KTOS", "empresa": "Kratos Defense", "mercado": "internacional", "cantidad": 18.77643409, "precio_compra": 47.93, "precio_actual": 50.98, "moneda": "USD"},
    {"ticker": "LITE", "empresa": "Lumentum Holdings", "mercado": "internacional", "cantidad": 0.01730106, "precio_compra": 867.00, "precio_actual": 914.76, "moneda": "USD"},
    {"ticker": "LLY", "empresa": "Eli Lilly", "mercado": "internacional", "cantidad": 2.97939101, "precio_compra": 775.83, "precio_actual": 1156.73, "moneda": "USD"},
    {"ticker": "LSCC", "empresa": "Lattice Semiconductor", "mercado": "internacional", "cantidad": 0.17427663, "precio_compra": 59.79, "precio_actual": 115.34, "moneda": "USD"},
    {"ticker": "MELI", "empresa": "MercadoLibre", "mercado": "internacional", "cantidad": 1.33591598, "precio_compra": 1876.89, "precio_actual": 1936.20, "moneda": "USD"},
    {"ticker": "META", "empresa": "Meta Platforms", "mercado": "internacional", "cantidad": 3.17152983, "precio_compra": 533.93, "precio_actual": 572.34, "moneda": "USD"},
    {"ticker": "MP", "empresa": "MP Materials", "mercado": "internacional", "cantidad": 19.87263231, "precio_compra": 60.38, "precio_actual": 54.75, "moneda": "USD"},
    {"ticker": "MRVL", "empresa": "Marvell Technology Group Ltd.", "mercado": "internacional", "cantidad": 4.68219531, "precio_compra": 256.29, "precio_actual": 211.66, "moneda": "USD"},
    {"ticker": "MSFT", "empresa": "Microsoft", "mercado": "internacional", "cantidad": 4.02524532, "precio_compra": 410.16, "precio_actual": 507.29, "moneda": "USD"},
    {"ticker": "MU", "empresa": "Micron Technology", "mercado": "internacional", "cantidad": 2.01440789, "precio_compra": 779.44, "precio_actual": 958.73, "moneda": "USD"},
    {"ticker": "NBIS", "empresa": "Nebius Group", "mercado": "internacional", "cantidad": 0.33396645, "precio_compra": 215.59, "precio_actual": 206.32, "moneda": "USD"},
    {"ticker": "NU", "empresa": "Nu Holdings", "mercado": "internacional", "cantidad": 370.08041037, "precio_compra": 13.05, "precio_actual": 14.55, "moneda": "USD"},
    {"ticker": "NVDA", "empresa": "Nvidia", "mercado": "internacional", "cantidad": 9.06006764, "precio_compra": 209.17, "precio_actual": 220.78, "moneda": "USD"},
    {"ticker": "OKLO", "empresa": "Oklo", "mercado": "internacional", "cantidad": 2.34147431, "precio_compra": 53.81, "precio_actual": 40.57, "moneda": "USD"},
    {"ticker": "PICK", "empresa": "iShares MSCI Global Metals", "mercado": "internacional", "cantidad": 1.05701068, "precio_compra": 29.40, "precio_actual": 65.20, "moneda": "USD"},
    {"ticker": "PURR", "empresa": "Hyperliquid Strategies", "mercado": "internacional", "cantidad": 33.27364077, "precio_compra": 6.01, "precio_actual": 12.25, "moneda": "USD"},
    {"ticker": "PWR", "empresa": "Quanta Services", "mercado": "internacional", "cantidad": 0.16480832, "precio_compra": 486.14, "precio_actual": 607.09, "moneda": "USD"},
    {"ticker": "QQQ", "empresa": "Invesco QQQ Trust", "mercado": "internacional", "cantidad": 0.68616911, "precio_compra": 0.00, "precio_actual": 716.76, "moneda": "USD"},
    {"ticker": "REMX", "empresa": "VanEck Rare Earth ETF", "mercado": "internacional", "cantidad": 8.92817736, "precio_compra": 106.10, "precio_actual": 77.52, "moneda": "USD"},
    {"ticker": "RKLB", "empresa": "Rocket Lab", "mercado": "internacional", "cantidad": 3.17299149, "precio_compra": 78.79, "precio_actual": 63.92, "moneda": "USD"},
    {"ticker": "RSP", "empresa": "Invesco S&P500 Equal Wght", "mercado": "internacional", "cantidad": 1.92360591, "precio_compra": 197.60, "precio_actual": 219.39, "moneda": "USD"},
    {"ticker": "SCHH", "empresa": "Schwab US REIT ETF", "mercado": "internacional", "cantidad": 47.74179114, "precio_compra": 19.80, "precio_actual": 23.58, "moneda": "USD"},
    {"ticker": "SCHP", "empresa": "Schwab US TIPS ETF", "mercado": "internacional", "cantidad": 4.27007590, "precio_compra": 25.03, "precio_actual": 25.91, "moneda": "USD"},
    {"ticker": "SQM", "empresa": "Sociedad Química y Minera", "mercado": "internacional", "cantidad": 113.44991868, "precio_compra": 41.69, "precio_actual": 79.01, "moneda": "USD"},
    {"ticker": "TSLA", "empresa": "Tesla", "mercado": "internacional", "cantidad": 1.88361700, "precio_compra": 425.13, "precio_actual": 367.95, "moneda": "USD"},
    {"ticker": "TSM", "empresa": "Taiwan Semiconductor", "mercado": "internacional", "cantidad": 6.32629707, "precio_compra": 322.52, "precio_actual": 415.32, "moneda": "USD"},
    {"ticker": "UBER", "empresa": "Uber Technologies", "mercado": "internacional", "cantidad": 8.31370375, "precio_compra": 72.17, "precio_actual": 75.65, "moneda": "USD"},
    {"ticker": "UNH", "empresa": "UnitedHealth Group", "mercado": "internacional", "cantidad": 9.12320054, "precio_compra": 303.23, "precio_actual": 389.41, "moneda": "USD"},
    {"ticker": "VBR", "empresa": "Vanguard Small Cap Value", "mercado": "internacional", "cantidad": 1.14157727, "precio_compra": 226.00, "precio_actual": 245.29, "moneda": "USD"},
    {"ticker": "VEU", "empresa": "Vanguard All World ex-US", "mercado": "internacional", "cantidad": 4.67833398, "precio_compra": 51.14, "precio_actual": 85.25, "moneda": "USD"},
    {"ticker": "VGSH", "empresa": "Vanguard Short Term Treas", "mercado": "internacional", "cantidad": 11.17702752, "precio_compra": 58.87, "precio_actual": 58.06, "moneda": "USD"},
    {"ticker": "VOO", "empresa": "Vanguard S&P 500 ETF", "mercado": "internacional", "cantidad": 8.89361596, "precio_compra": 472.65, "precio_actual": 704.89, "moneda": "USD"},
    {"ticker": "VRT", "empresa": "Vertiv Holdings", "mercado": "internacional", "cantidad": 0.51220511, "precio_compra": 212.61, "precio_actual": 258.72, "moneda": "USD"},
    {"ticker": "VT", "empresa": "Vanguard Total World Stock", "mercado": "internacional", "cantidad": 34.14496874, "precio_compra": 132.00, "precio_actual": 160.55, "moneda": "USD"},
    {"ticker": "VTI", "empresa": "Vanguard Total Stock Market", "mercado": "internacional", "cantidad": 8.87858262, "precio_compra": 271.78, "precio_actual": 378.15, "moneda": "USD"},
    {"ticker": "VTV", "empresa": "Vanguard Value ETF", "mercado": "internacional", "cantidad": 12.34565141, "precio_compra": 181.40, "precio_actual": 224.85, "moneda": "USD"},
    {"ticker": "VWO", "empresa": "Vanguard FTSE Emg Mkts ETF", "mercado": "internacional", "cantidad": 14.77957742, "precio_compra": 53.79, "precio_actual": 60.52, "moneda": "USD"},
    {"ticker": "VXUS", "empresa": "Vanguard Total Intl Stock", "mercado": "internacional", "cantidad": 51.47776980, "precio_compra": 66.82, "precio_actual": 87.32, "moneda": "USD"},
    {"ticker": "WMT", "empresa": "Walmart", "mercado": "internacional", "cantidad": 6.54668540, "precio_compra": 106.97, "precio_actual": 104.87, "moneda": "USD"},
    {"ticker": "DWBDS", "empresa": "Cash Sweep DriveWealth", "mercado": "internacional", "cantidad": 44.27, "precio_compra": 1.00, "precio_actual": 1.00, "moneda": "USD"},
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
