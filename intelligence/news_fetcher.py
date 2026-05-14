# ============================================================
# NEWS FETCHER — Inteligencia de Mercado
# Descarga noticias de RSS, filtra por relevancia a la cartera,
# y guarda en Supabase (market_news).
# Uso:
#   python -m intelligence.news_fetcher
#   python -m intelligence.news_fetcher --hours 6
# ============================================================

import sys, re, argparse, time
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, ".")

import feedparser
from database.supabase_client import get_client


# ── FUENTES RSS (sin API keys) ───────────────────────────────
# Mezcla de macro global, finanzas y noticias específicas de Chile
RSS_FEEDS = [
    # === GLOBAL / EEUU ===
    {"nombre": "Yahoo Finance Markets",
     "url":    "https://finance.yahoo.com/news/rssindex",
     "tipo":   "global"},
    {"nombre": "MarketWatch Top Stories",
     "url":    "https://feeds.marketwatch.com/marketwatch/topstories/",
     "tipo":   "global"},
    {"nombre": "Investing.com Markets",
     "url":    "https://www.investing.com/rss/news_25.rss",
     "tipo":   "global"},
    {"nombre": "CNBC Top News",
     "url":    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
     "tipo":   "global"},
    {"nombre": "SeekingAlpha Market Currents",
     "url":    "https://seekingalpha.com/market_currents.xml",
     "tipo":   "global"},

    # === CHILE / LATAM ===
    {"nombre": "Diario Financiero",
     "url":    "https://www.df.cl/feed",
     "tipo":   "chile"},
    {"nombre": "La Tercera Pulso",
     "url":    "https://www.latercera.com/pulso/feed/",
     "tipo":   "chile"},
    {"nombre": "El Mostrador Mercados",
     "url":    "https://www.elmostrador.cl/mercados/feed/",
     "tipo":   "chile"},

    # === CRYPTO ===
    {"nombre": "CoinDesk",
     "url":    "https://www.coindesk.com/arc/outboundfeeds/rss/",
     "tipo":   "crypto"},
    {"nombre": "Cointelegraph",
     "url":    "https://cointelegraph.com/rss",
     "tipo":   "crypto"},
]

# Por ticker específico (Yahoo Finance) — se construye dinámicamente
def yf_ticker_rss(ticker: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


# ── KEYWORDS MACRO QUE MUEVEN MERCADOS ──────────────────────
MACRO_KEYWORDS = {
    "Fed/Tasas EEUU":      ["federal reserve", "fed ", "powell", "interest rate", "fomc", "rate cut", "rate hike", "treasury yield"],
    "Inflación":           ["inflation", "cpi ", "ppi ", "core inflation", "ipc "],
    "Recesión":            ["recession", "gdp ", "unemployment", "jobs report", "payroll"],
    "Geopolítica":         ["war ", "tariff", "trade war", "sanctions", "china us", "taiwan", "ukraine", "russia"],
    "Earnings":            ["earnings beat", "earnings miss", "guidance", "quarterly results", "q1 earnings", "q2 earnings", "q3 earnings", "q4 earnings"],
    "Chile":               ["chile ", "banco central de chile", "bcch", "tpm ", "imacec", "peso chileno"],
    "Crypto":              ["bitcoin", "btc ", "ethereum", "eth ", "crypto", "satoshi"],
}

# Sectores y sinónimos
SECTOR_KEYWORDS = {
    "Tecnología":          ["tech ", "technology", "software", "semiconductors", "chips", "ai ", "artificial intelligence"],
    "Financiero":          ["bank ", "banking", "financial", "insurance"],
    "Energía":             ["oil ", "crude", "opec", "energy ", "renewable"],
    "Salud":               ["pharma", "healthcare", "biotech", "fda "],
    "Retail/Consumo":      ["retail ", "consumer", "amazon", "walmart"],
    "Aviación":            ["airline", "boeing", "airbus", "aviation"],
    "Minería":             ["copper", "lithium", "mining", "cobre", "litio"],
}


# ── HELPERS ──────────────────────────────────────────────────
def get_portfolio_tickers() -> set[str]:
    """Lee la cartera actual desde Supabase y retorna tickers únicos."""
    sb = get_client()
    r = sb.table("cartera_actual").select("ticker,mercado").execute()
    tickers = set()
    for row in r.data:
        tk = (row.get("ticker") or "").upper().strip()
        if tk and tk != "PORTFOLIO_CL":
            tickers.add(tk)
    return tickers


def detect_tickers(text: str, portfolio: set[str]) -> list[str]:
    """
    Detecta menciones de tickers en el texto.
    Match por palabra completa para evitar falsos positivos (e.g. 'BCI' ≠ 'BCIDAD').
    """
    matches = []
    text_upper = " " + text.upper() + " "
    for tk in portfolio:
        # Buscar como palabra completa con espacios/puntuación alrededor
        pattern = r"[^A-Z0-9]" + re.escape(tk) + r"[^A-Z0-9]"
        if re.search(pattern, text_upper):
            matches.append(tk)
    return matches


def detect_sectors(text: str) -> list[str]:
    """Detecta sectores mencionados en el texto."""
    text_lower = text.lower()
    found = []
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            found.append(sector)
    return found


def calc_relevancia_preliminar(tickers_found: list, sectors_found: list, text: str) -> int:
    """
    Score 0-100 basado en heurísticas simples:
    - +40 por cada ticker propio mencionado (max 80)
    - +10 por cada sector relevante (max 30)
    - +15 si hay keywords macro de alto impacto
    """
    score = 0
    score += min(len(tickers_found) * 40, 80)
    score += min(len(sectors_found) * 10, 30)

    text_lower = text.lower()
    macro_hit = sum(
        1 for kws in MACRO_KEYWORDS.values()
        for kw in kws if kw in text_lower
    )
    if macro_hit > 0:
        score += min(15, macro_hit * 5)

    return min(score, 100)


def parse_entry_date(entry) -> Optional[datetime]:
    """Extrae fecha del entry RSS, devuelve UTC datetime o None."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def clean_text(s: Optional[str]) -> str:
    """Limpia HTML y normaliza espacios."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1500]  # cap a 1500 chars para no explotar storage


# ── FETCH PRINCIPAL ──────────────────────────────────────────
def fetch_all(hours_back: int = 24) -> list[dict]:
    """
    Descarga todas las fuentes y retorna lista de noticias parseadas.
    Filtra por fecha (últimas N horas) y por relevancia preliminar.
    """
    portfolio = get_portfolio_tickers()
    print(f"📊 Cartera: {len(portfolio)} tickers únicos")
    print(f"⏰ Buscando noticias de las últimas {hours_back}h\n")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    all_news = []

    # === Feeds globales ===
    for source in RSS_FEEDS:
        try:
            print(f"  📡 {source['nombre']}...", end=" ")
            feed = feedparser.parse(source["url"])
            kept = 0
            for entry in feed.entries[:50]:
                fecha = parse_entry_date(entry)
                if fecha and fecha < cutoff:
                    continue

                titulo = clean_text(entry.get("title"))
                resumen = clean_text(entry.get("summary") or entry.get("description"))
                url = entry.get("link", "")
                texto_completo = f"{titulo} {resumen}"

                tickers = detect_tickers(texto_completo, portfolio)
                sectores = detect_sectors(texto_completo)
                relevancia = calc_relevancia_preliminar(tickers, sectores, texto_completo)

                # Filtro: guardar si hay ticker propio, o macro relevante, o sector
                if relevancia < 15 and not tickers:
                    continue

                all_news.append({
                    "fecha_noticia": fecha.isoformat() if fecha else datetime.now(timezone.utc).isoformat(),
                    "titulo": titulo,
                    "resumen": resumen,
                    "url": url,
                    "fuente": source["nombre"],
                    "tickers_mencionados": tickers,
                    "sectores_mencionados": sectores,
                    "relevancia_preliminar": relevancia,
                    "procesado_ai": False,
                })
                kept += 1
            print(f"{kept} relevantes")
        except Exception as e:
            print(f"❌ error: {e}")

    # === Feeds por ticker ===
    # Tomar top 10 tickers por valor para no saturar
    print(f"\n  📡 Yahoo Finance por ticker (top 10 cartera)...")
    sb = get_client()
    cart = sb.table("cartera_actual").select("ticker").execute()
    top_tickers = list({(r.get("ticker") or "").upper() for r in cart.data
                        if r.get("ticker") and r.get("ticker") != "PORTFOLIO_CL"})[:10]

    for tk in top_tickers:
        try:
            feed = feedparser.parse(yf_ticker_rss(tk))
            for entry in feed.entries[:10]:
                fecha = parse_entry_date(entry)
                if fecha and fecha < cutoff:
                    continue
                titulo = clean_text(entry.get("title"))
                resumen = clean_text(entry.get("summary"))
                all_news.append({
                    "fecha_noticia": fecha.isoformat() if fecha else datetime.now(timezone.utc).isoformat(),
                    "titulo": titulo,
                    "resumen": resumen,
                    "url": entry.get("link", ""),
                    "fuente": f"Yahoo Finance ({tk})",
                    "tickers_mencionados": [tk],
                    "sectores_mencionados": detect_sectors(f"{titulo} {resumen}"),
                    "relevancia_preliminar": 75,  # match directo de ticker
                    "procesado_ai": False,
                })
        except Exception as e:
            print(f"    ❌ {tk}: {e}")

    return all_news


# ── INSERTAR EN SUPABASE ─────────────────────────────────────
def save_news(news_list: list[dict]) -> dict:
    """Inserta noticias en Supabase. Dedupea por URL."""
    if not news_list:
        return {"insertadas": 0, "duplicadas": 0, "errores": 0}

    sb = get_client()

    # Cargar URLs ya existentes (paginado)
    existing_urls = set()
    page = 0
    while True:
        r = sb.table("market_news").select("url").range(page*1000, page*1000+999).execute()
        existing_urls.update(row["url"] for row in r.data if row.get("url"))
        if len(r.data) < 1000:
            break
        page += 1

    ins = dup = err = 0
    for n in news_list:
        if n["url"] in existing_urls:
            dup += 1
            continue
        try:
            sb.table("market_news").insert(n).execute()
            existing_urls.add(n["url"])
            ins += 1
        except Exception as e:
            # Probablemente conflict de URL única → contar como duplicado
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                dup += 1
            else:
                err += 1
                if err <= 3:
                    print(f"  ❌ Error: {str(e)[:120]}")

    return {"insertadas": ins, "duplicadas": dup, "errores": err}


# ── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24,
                        help="Buscar noticias de las últimas N horas (default 24)")
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 NEWS FETCHER — Inteligencia de Mercado")
    print("=" * 60)

    t0 = time.time()
    news = fetch_all(hours_back=args.hours)
    print(f"\n📰 Total recolectadas: {len(news)} noticias\n")

    if news:
        result = save_news(news)
        print(f"✅ Insertadas: {result['insertadas']}")
        print(f"⏭  Duplicadas: {result['duplicadas']}")
        print(f"❌ Errores:    {result['errores']}")

    print(f"\n⏱  Tiempo: {time.time()-t0:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
