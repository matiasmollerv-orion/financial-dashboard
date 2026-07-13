# ============================================================
# DISCOVERY v1 — Visibilidad de jugadores nuevos FUERA del universo
#
# Todo el resto del sistema (opportunity_detector, sell_engine,
# news_fetcher) es ciego por diseño: solo ve tickers que YA conoce
# (cartera + watchlist.yaml + investor_profile.yaml). Este módulo
# invierte esa lógica — busca activamente lo que el sistema NO sabe
# que existe, en 3 fuentes gratuitas (más gbrain_bridge.py para
# newsletters, que corre localmente):
#
#   1. 13F de smart money — emisores que NO reconocemos por nombre.
#      Si Druckenmiller compra algo nuevo, hoy se descarta en
#      silencio (match_ticker devuelve None). Aquí se reporta.
#   2. Escáner de IPOs (S-1) — SEC EDGAR full-text-search por las
#      palabras_clave de cada vertical. Detecta empresas ANTES de
#      ser conocidas, al momento de registrar su salida a bolsa.
#   3. Menciones en noticias ya recolectadas — market_news (que
#      news_fetcher.py ya llena a diario) contiene artículos
#      relevantes por sector/macro aunque no mencionen un ticker
#      conocido. Se escanean por cashtags ($TICKER) nuevos.
#
# Cadencia: SEMANAL (a pedido explícito de Matías — son eventos de
# baja frecuencia, no hace falta verlos a diario). Corre desde
# discovery-weekly.yml, separado del pipeline diario.
#
# Severidad SIEMPRE "info" — esto NO es una señal de compra, es
# "esto existe, evalúalo". Nunca se mezcla con las alertas técnicas.
#
# CERO llamadas a la API de Anthropic.
#
# Uso:
#   python -m intelligence.discovery
#   python -m intelligence.discovery --dry-run --days 10
# ============================================================

import sys, time, re, argparse, warnings
from datetime import date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import yaml
import requests
import pandas as pd
from pathlib import Path

from database.supabase_client import get_client
from intelligence.edgar_monitor import (
    _get, _fetch_13f_holdings, match_ticker, HEADERS, THROTTLE,
)

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"
PROFILE_PATH = Path(__file__).parent / "config" / "investor_profile.yaml"

_session = requests.Session()
_session.headers.update(HEADERS)


# ── UNIVERSO CONOCIDO + VALIDACIÓN SEC ──────────────────────
def load_known_universe() -> set:
    """Todo ticker que el sistema YA conoce — cartera, watchlist, perfil."""
    tks = set()
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            wl = yaml.safe_load(f)
        for r in wl.get("recurrente", []):
            tks.add(r["ticker"])
        for tier in ("tier1", "tier2", "tier3"):
            for i in wl.get("watchlist", {}).get(tier, []):
                tks.add(i["ticker"])
        for i in wl.get("acciones_pendientes", []):
            tks.add(i.get("ticker", ""))
    except Exception:
        pass
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            prof = yaml.safe_load(f)
        for vert in prof.get("verticales", {}).values():
            tks.update(vert.get("tickers", {}).keys())
            tks.update(vert.get("candidatos_evaluar", []))
            tks.update(vert.get("vender", []))
        tks.update(prof.get("core", {}).get("tickers", []))
        tks.update(prof.get("diversificadores_renta_fija", {}).get("tickers", {}).keys())
    except Exception:
        pass
    try:
        sb = get_client()
        r = sb.table("cartera_actual").select("ticker").execute()
        tks.update(row["ticker"] for row in r.data if row.get("ticker") != "PORTFOLIO_CL")
    except Exception:
        pass
    return {t for t in tks if t}


def load_vertical_keywords() -> dict:
    """vertical → lista de palabras_clave, desde investor_profile.yaml."""
    with open(PROFILE_PATH, encoding="utf-8") as f:
        prof = yaml.safe_load(f)
    return {name: v.get("palabras_clave", []) for name, v in prof.get("verticales", {}).items()}


_SEC_TICKER_MAP = None


def load_sec_ticker_map() -> dict:
    """ticker → nombre de empresa, desde el mapping oficial de la SEC.
    Cacheado en memoria — un solo fetch por corrida."""
    global _SEC_TICKER_MAP
    if _SEC_TICKER_MAP is not None:
        return _SEC_TICKER_MAP
    try:
        data = _get("https://www.sec.gov/files/company_tickers.json")
        _SEC_TICKER_MAP = {row["ticker"].upper(): row["title"] for row in data.values()}
    except Exception as e:
        print(f"  Error bajando company_tickers: {e}")
        _SEC_TICKER_MAP = {}
    return _SEC_TICKER_MAP


MEGA_CAP_USD = 30_000_000_000  # sobre esto, no es "descubrimiento" — ya lo conoces


def filter_mega_caps(tickers: set) -> set:
    """Descarta tickers con market cap > MEGA_CAP_USD. Una empresa de
    USD 30B+ (Apple, NASDAQ Inc, Dollar General...) no es un descubrimiento
    aunque no esté en tu watchlist — es simplemente algo que no tienes.
    El valor del escáner está en lo que SÍ es genuinamente poco conocido."""
    if not tickers:
        return tickers
    try:
        import yfinance as yf
    except ImportError:
        return tickers
    keep = set()
    for tk in tickers:
        try:
            cap = yf.Ticker(tk).info.get("marketCap")
            if cap is None or cap <= MEGA_CAP_USD:
                keep.add(tk)
        except Exception:
            keep.add(tk)  # si falla el check, no descartar por las dudas
    return keep


def extract_cashtags(text: str) -> set:
    """Cashtags $TICKER (1-5 letras) en el texto. Útil para newsletters/
    fuentes estilo Twitter — la mayoría de RSS financiero tradicional NO
    usa este formato (usa nombre de empresa: "Nvidia", no "$NVDA")."""
    return {m.upper() for m in re.findall(r"\$([A-Za-z]{1,5})\b", text or "")}


_SEC_NAME_INDEX = None
STOP_FIRST_WORDS = {"the", "new", "global", "american", "national", "first",
                    "united", "big", "one", "this", "that", "here", "how"}


def load_sec_name_index() -> dict:
    """primera_palabra_normalizada -> [(ticker, nombre_completo), ...].
    Heurística de matching por nombre de empresa (los titulares de noticias
    dicen 'Nvidia', no '$NVDA' ni 'NVIDIA Corp'). Solo incluye palabras
    DISTINTIVAS — si >3 empresas SEC comparten la primera palabra ("Bank",
    "Blackrock", "Western"...) no sirve para identificar una empresa
    específica y se descarta (evita cientos de falsos positivos)."""
    global _SEC_NAME_INDEX
    if _SEC_NAME_INDEX is not None:
        return _SEC_NAME_INDEX
    sec_map = load_sec_ticker_map()
    raw = {}
    for tk, name in sec_map.items():
        words = re.sub(r"[^a-zA-Z0-9 ]", "", name).lower().split()
        if not words:
            continue
        first = words[0]
        if len(first) < 5 or first in STOP_FIRST_WORDS:
            continue
        raw.setdefault(first, []).append((tk, name))
    idx = {k: v for k, v in raw.items() if len(v) <= 3}
    _SEC_NAME_INDEX = idx
    return idx


def extract_company_mentions(text: str, name_index: dict, known_universe: set) -> set:
    """Extrae frases de 2+ palabras capitalizadas consecutivas y las matchea
    contra la primera palabra distintiva de nombres de empresa SEC.

    Exige 2+ palabras (no 1) porque los titulares financieros usan Title
    Case ("1 Big Reason to Buy FuelCell Energy Stock") — con 1 palabra,
    "Stock", "Big", "Buy" matchean nombres de empresa por accidente.
    Con 2+ palabras consecutivas el ruido baja drásticamente: "FuelCell
    Energy" es una frase real, "Big Reason" no matchea ninguna empresa."""
    found = set()
    for phrase in re.findall(r"\b[A-Z][a-zA-Z']{2,}(?:\s[A-Z][a-zA-Z']{2,}){1,3}\b", text or ""):
        primera = phrase.split()[0].lower()
        candidatos = name_index.get(primera)
        if not candidatos:
            continue
        for tk, _ in candidatos:
            if tk not in known_universe:
                found.add(tk)
    return found


# ── 1. 13F — EMISORES NO RECONOCIDOS ────────────────────────
def scan_13f_unrecognized(known_universe: set, days: int) -> list:
    """Cuando un fondo de smart money compra/aumenta algo que ni siquiera
    está en NAME_ALIASES (match_ticker de edgar_monitor no lo resuelve),
    hoy se descarta en silencio. Aquí se reporta con el nombre crudo del
    emisor para que Matías decida si vale la pena investigar."""
    alerts = []
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl = yaml.safe_load(f)
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    for fund in wl.get("smart_money_funds", []):
        try:
            cik = int(fund["cik"])
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", [])

            f13 = [(dates[i], accs[i]) for i, f in enumerate(forms) if f == "13F-HR"]
            if not f13 or f13[0][0] < cutoff:
                continue

            curr = _fetch_13f_holdings(cik, f13[0][1])
            prev = _fetch_13f_holdings(cik, f13[1][1]) if len(f13) > 1 else {}
            if not curr:
                continue

            for issuer, val in curr.items():
                tk = match_ticker(issuer)
                if tk:
                    continue  # ya lo reconocemos — lo maneja check_13f normal
                if issuer.upper() in known_universe:
                    continue
                prev_val = prev.get(issuer, 0)
                if prev_val > 0 and val <= prev_val * 1.5:
                    continue  # no es posición nueva ni aumento fuerte
                tipo = "POSICIÓN NUEVA" if prev_val == 0 else "AUMENTÓ fuerte"
                alerts.append({
                    "categoria":  "descubrimiento",
                    "severidad":  "info",
                    "activo":     issuer[:60],
                    "titulo":     f"DESCUBRIMIENTO 13F: {fund['pm']} — {tipo} en {issuer[:40]}",
                    "mensaje":    f"{fund['nombre']} ({fund['pm']}) reportó {tipo.lower()} en "
                                  f"'{issuer}' — USD {val*1000:,.0f}. No reconocemos este emisor "
                                  f"(no está en tu watchlist ni en la lista de alias conocidos). "
                                  f"Filing del {f13[0][0]}.",
                    "metricas":   {"fuente": "13f", "fondo": fund["nombre"], "pm": fund["pm"],
                                   "valor_usd": val * 1000, "tipo": tipo},
                    "sugerencia": f"Buscar '{issuer}' para identificar el ticker y evaluar si "
                                  f"merece entrar a la watchlist.",
                })
        except Exception as e:
            print(f"  {fund.get('nombre', '?')}: {str(e)[:80]}")
    return alerts


# ── 2. ESCÁNER DE IPOs (S-1) ─────────────────────────────────
def scan_new_ipos(vertical_keywords: dict, days: int) -> list:
    """SEC EDGAR full-text-search sobre S-1 nuevos, por palabra clave de
    cada vertical. Detecta empresas ANTES de ser conocidas — al momento
    de registrar su salida a bolsa, no después de que ya subieron 200%.

    Agrupa por CIK (una empresa = una alerta), aunque matchee varias
    verticales/keywords — evita duplicados que choquen contra el
    constraint uniq_alert_per_day de portfolio_alerts."""
    start = (date.today() - timedelta(days=days)).isoformat()
    end = date.today().isoformat()
    por_cik = {}  # cik -> {"nombre", "form", "fecha", "adsh", "matches": [(vertical, kw), ...]}

    for vertical, keywords in vertical_keywords.items():
        for kw in keywords[:3]:  # cap por vertical para no saturar EDGAR
            try:
                q = requests.utils.quote(f'"{kw}"')
                url = (f"https://efts.sec.gov/LATEST/search-index?q={q}&forms=S-1"
                       f"&dateRange=custom&startdt={start}&enddt={end}")
                time.sleep(THROTTLE)
                r = _session.get(url, timeout=20)
                r.raise_for_status()
                data = r.json()
                hits = data.get("hits", {}).get("hits", [])
                for h in hits[:5]:  # top 5 por keyword
                    src = h.get("_source", {})
                    ciks = src.get("ciks", [])
                    cik = ciks[0] if ciks else None
                    if not cik:
                        continue
                    entry = por_cik.setdefault(cik, {
                        "nombre": (src.get("display_names") or ["?"])[0],
                        "form": src.get("form", "S-1"),
                        "fecha": src.get("file_date", "?"),
                        "adsh": src.get("adsh", "").replace("-", ""),
                        "matches": [],
                    })
                    if (vertical, kw) not in entry["matches"]:
                        entry["matches"].append((vertical, kw))
            except Exception as e:
                print(f"  IPO scan '{kw}' ({vertical}): {str(e)[:80]}")

    alerts = []
    for cik, info in por_cik.items():
        nombre = info["nombre"]
        verticales = sorted({v for v, _ in info["matches"]})
        kw_str = ", ".join(f"'{kw}'" for _, kw in info["matches"][:3])
        link = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
               f"&CIK={cik}&type=S-1") if not info["adsh"] else \
               f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{info['adsh']}"
        alerts.append({
            "categoria":  "descubrimiento",
            "severidad":  "info",
            "activo":     nombre[:60],
            "titulo":     f"NUEVO IPO: {nombre[:50]} ({', '.join(verticales)})",
            "mensaje":    f"{nombre} presentó {info['form']} el {info['fecha']}, mencionando "
                          f"{kw_str} — coincide con {'tu vertical' if len(verticales)==1 else 'tus verticales'} "
                          f"'{', '.join(verticales)}'. Empresa aún no está en tu radar.",
            "metricas":   {"fuente": "ipo_s1", "verticales": verticales,
                           "fecha_filing": info["fecha"], "form": info["form"]},
            "sugerencia": f"Revisar el filing en {link} — evaluar si merece "
                          f"entrar a la watchlist antes de que sea conocida.",
        })
    return alerts


# ── 3. MENCIONES NUEVAS EN NOTICIAS YA RECOLECTADAS ─────────
def scan_news_mentions(known_universe: set, sec_map: dict, days: int) -> list:
    """market_news ya se llena a diario con artículos relevantes por sector/
    macro (news_fetcher.py), incluso sin mencionar un ticker conocido. Aquí
    se escanean esos artículos por cashtags nuevos, validados contra la
    lista oficial de la SEC para filtrar ruido."""
    alerts = []
    sb = get_client()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        r = (sb.table("market_news").select("titulo,resumen,url,fuente,fecha_noticia,sectores_mencionados")
             .gte("fecha_noticia", cutoff)
             .limit(500).execute())
        rows = r.data
    except Exception as e:
        print(f"  Error leyendo market_news: {str(e)[:80]}")
        return alerts

    # Solo artículos que news_fetcher.py YA marcó como relevantes a un
    # sector temático (SECTOR_KEYWORDS) — filtra ruido genérico de mercado
    # (ej. "NASDAQ", "Apple" apareciendo en cualquier artículo financiero
    # sin relación real con las verticales de Matías).
    rows_relevantes = [row for row in rows if row.get("sectores_mencionados")]

    name_index = load_sec_name_index()
    encontrados = {}  # ticker -> {"articulos": [...], "via_cashtag": bool}
    for row in rows_relevantes:
        texto = f"{row.get('titulo', '')} {row.get('resumen', '')}"
        # Vía 1: cashtags $TICKER — señal fuerte, sin ambigüedad, basta 1 mención
        for tk in extract_cashtags(texto):
            if tk in known_universe or tk not in sec_map:
                continue
            e = encontrados.setdefault(tk, {"articulos": [], "via_cashtag": False})
            e["articulos"].append(row)
            e["via_cashtag"] = True
        # Vía 2: nombre de empresa multi-palabra — señal más débil, se exige
        # repetición (ver filtro min_menciones más abajo)
        for tk in extract_company_mentions(texto, name_index, known_universe):
            e = encontrados.setdefault(tk, {"articulos": [], "via_cashtag": False})
            e["articulos"].append(row)

    # Pre-filtro por menciones antes del check de market cap (más caro)
    candidatos = {tk: info for tk, info in encontrados.items()
                 if info["via_cashtag"] or len(info["articulos"]) >= 2}
    no_mega = filter_mega_caps(set(candidatos.keys()))

    for tk, info in candidatos.items():
        if tk not in no_mega:
            continue  # mega-cap conocida — no es un "descubrimiento"
        articulos = info["articulos"]
        n = len(articulos)
        art = articulos[0]
        empresa = sec_map.get(tk, "?")
        alerts.append({
            "categoria":  "descubrimiento",
            "severidad":  "info",
            "activo":     tk,
            "titulo":     f"NUEVA MENCIÓN: {empresa[:40]} ({tk})",
            "mensaje":    f"{empresa} ({tk}) mencionado en {n} artículo(s) reciente(s), "
                          f"no está en tu watchlist. Ejemplo: "
                          f"'{art.get('titulo', '')[:100]}' — {art.get('fuente', '?')}.",
            "metricas":   {"fuente": "noticias", "menciones": n,
                           "empresa": empresa, "url_ejemplo": art.get("url", "")},
            "sugerencia": "Evaluar si merece incorporarse a la watchlist.",
        })
    return alerts


# ── SAVE ────────────────────────────────────────────────────
def save_alerts(alerts: list) -> dict:
    sb = get_client()
    ins = err = 0
    try:
        sb.table("portfolio_alerts").update({"activo_alerta": False}) \
          .eq("activo_alerta", True).eq("categoria", "descubrimiento").execute()
    except Exception:
        pass
    if not alerts:
        return {"insertadas": 0, "errores": 0}
    for a in alerts:
        try:
            sb.table("portfolio_alerts").insert(a).execute()
            ins += 1
        except Exception as e:
            err += 1
            if err <= 3:
                print(f"  {a['activo']}: {str(e)[:100]}")
    return {"insertadas": ins, "errores": err}


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=10,
                        help="Ventana de días para 13F/IPOs/noticias (default 10)")
    args = parser.parse_args()

    print("=" * 60)
    print("DISCOVERY v1 — Visibilidad de jugadores nuevos")
    print("=" * 60)

    known = load_known_universe()
    print(f"\nUniverso conocido: {len(known)} tickers")

    print("Bajando lista oficial de tickers SEC...")
    sec_map = load_sec_ticker_map()
    print(f"  {len(sec_map)} tickers SEC")

    keywords = load_vertical_keywords()

    all_alerts = []

    print(f"\n[1/3] 13F smart money — emisores no reconocidos ({args.days}d)...")
    a1 = scan_13f_unrecognized(known, args.days)
    all_alerts.extend(a1)
    print(f"  {len(a1)} descubrimientos")

    print(f"[2/3] Escáner de IPOs (S-1) por vertical ({args.days}d)...")
    a2 = scan_new_ipos(keywords, args.days)
    all_alerts.extend(a2)
    print(f"  {len(a2)} descubrimientos")

    print(f"[3/3] Menciones nuevas en noticias ya recolectadas ({args.days}d)...")
    a3 = scan_news_mentions(known, sec_map, args.days)
    all_alerts.extend(a3)
    print(f"  {len(a3)} descubrimientos")

    print(f"\nTotal: {len(all_alerts)} descubrimientos")
    for a in all_alerts[:15]:
        print(f"  [{(a['metricas'] or {}).get('fuente', '?'):10s}] {a['titulo']}")

    if args.dry_run:
        print("\nDRY RUN — no se guardó nada")
        return
    result = save_alerts(all_alerts)
    print(f"\nInsertadas: {result['insertadas']} | Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
