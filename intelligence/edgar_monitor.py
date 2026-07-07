# ============================================================
# EDGAR MONITOR v1 — Detección temprana desde SEC EDGAR (gratis)
#
# Señales que PRECEDEN al precio (a diferencia de los dips):
#
#   1. Form 4 — compras de insiders (transaction code P).
#      Cluster buys (2+ insiders distintos en 14 días) es la señal
#      predictiva mejor validada académicamente.
#   2. 8-K — eventos materiales con item codes (resultados,
#      acuerdos, salidas de ejecutivos).
#   3. 13F-HR — holdings trimestrales de los 15 fondos smart money
#      (CIKs en watchlist.yaml). Al detectar un filing nuevo, hace
#      diff contra el anterior y alerta posiciones nuevas/aumentadas
#      que intersectan con tu universo.
#
# APIs públicas SEC (sin key, requiere User-Agent):
#   https://www.sec.gov/files/company_tickers.json
#   https://data.sec.gov/submissions/CIK##########.json
#   https://www.sec.gov/Archives/edgar/data/...
#
# Uso:
#   python -m intelligence.edgar_monitor
#   python -m intelligence.edgar_monitor --dry-run --days 7
# ============================================================

import sys, time, argparse, warnings, re
from datetime import date, timedelta
import xml.etree.ElementTree as ET
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

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"
HEADERS = {"User-Agent": "FinancialDashboard personal matiasmollerv@gmail.com"}
THROTTLE = 0.15  # SEC pide max ~10 req/s

# Aliases nombre-de-emisor → ticker para matchear 13F (que usa nombres, no tickers)
NAME_ALIASES = {
    "NVIDIA": "NVDA", "MICROSOFT": "MSFT", "ALPHABET": "GOOGL", "AMAZON": "AMZN",
    "MERCADOLIBRE": "MELI", "NU HOLDINGS": "NU", "TAIWAN SEMICONDUCTOR": "TSM",
    "ASML": "ASML", "MICRON": "MU", "BROADCOM": "AVGO", "MARVELL": "MRVL",
    "UBER": "UBER", "ADVANCED MICRO": "AMD", "PALO ALTO": "PANW",
    "ELI LILLY": "LLY", "UNITEDHEALTH": "UNH", "COREWEAVE": "CRWV",
    "NEBIUS": "NBIS", "OKLO": "OKLO", "IONQ": "IONQ", "CAMECO": "CCJ",
    "ARES MANAGEMENT": "ARES", "KRATOS": "KTOS", "ROCKET LAB": "RKLB",
    "CEREBRAS": "CBRS", "ROBINHOOD": "HOOD", "SOFI": "SOFI",
    "COHERENT": "COHR", "AEROVIRONMENT": "AVAV", "GE VERNOVA": "GEV",
    "VISTRA": "VST", "SYMBOTIC": "SYM", "QUALCOMM": "QCOM",
    "LATTICE": "LSCC", "MP MATERIALS": "MP", "BLOOM ENERGY": "BE",
}


# ── HELPERS ─────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update(HEADERS)


def _get(url: str, as_json: bool = True):
    time.sleep(THROTTLE)
    r = _session.get(url, timeout=20)
    r.raise_for_status()
    return r.json() if as_json else r.text


def load_ticker_ciks(tickers: set) -> dict:
    """ticker → CIK (int) desde el mapping oficial de la SEC."""
    try:
        data = _get("https://www.sec.gov/files/company_tickers.json")
    except Exception as e:
        print(f"  Error bajando company_tickers: {e}")
        return {}
    out = {}
    for row in data.values():
        tk = row.get("ticker", "").upper()
        if tk in tickers:
            out[tk] = int(row["cik_str"])
    return out


def build_universe() -> dict:
    """Tickers a monitorear: cartera intl > USD 1000 + recurrente + tier1/tier2."""
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl = yaml.safe_load(f)
    universe = {}
    for r in wl.get("recurrente", []):
        universe[r["ticker"]] = "recurrente"
    for tier in ("tier1", "tier2"):
        for i in wl.get("watchlist", {}).get(tier, []):
            universe.setdefault(i["ticker"], tier)
    try:
        sb = get_client()
        r = sb.table("cartera_actual").select("ticker,mercado,cantidad,precio_actual").execute()
        for row in r.data:
            if row.get("mercado") != "internacional":
                continue
            try:
                val = float(row["cantidad"]) * float(row["precio_actual"])
            except (TypeError, ValueError):
                continue
            if val >= 1000:
                universe.setdefault(row["ticker"], "cartera")
    except Exception as e:
        print(f"  Warning cartera: {e}")
    # ETFs no tienen insiders — excluir los core
    for etf in wl.get("etfs_core_no_alert", []):
        universe.pop(etf, None)
    return universe


# ── 1. FORM 4 — INSIDER BUYS ────────────────────────────────
def parse_form4(xml_text: str) -> list:
    """Extrae compras (code P, adquisición A) de un Form 4. → [(owner, shares, price)]"""
    buys = []
    try:
        root = ET.fromstring(xml_text)
        owners = [o.findtext(".//rptOwnerName") or "?" for o in root.findall(".//reportingOwner")]
        owner = owners[0] if owners else "?"
        for tx in root.findall(".//nonDerivativeTransaction"):
            code = tx.findtext(".//transactionCode")
            adq = tx.findtext(".//transactionAcquiredDisposedCode/value")
            if code != "P" or adq != "A":
                continue
            shares = float(tx.findtext(".//transactionShares/value") or 0)
            price = float(tx.findtext(".//transactionPricePerShare/value") or 0)
            buys.append((owner, shares, price))
    except Exception:
        pass
    return buys


def check_insider_buys(ciks: dict, days: int) -> list:
    """Form 4 con compras reales en los últimos N días. Cluster = 2+ insiders."""
    alerts = []
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    for tk, cik in ciks.items():
        try:
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])

            form4_idx = [i for i, (f, d) in enumerate(zip(forms, dates))
                         if f == "4" and d >= cutoff][:8]  # cap por ticker
            if not form4_idx:
                continue

            buyers = {}  # owner → total USD
            for i in form4_idx:
                acc = accs[i].replace("-", "")
                doc = docs[i]
                # primaryDocument a veces viene con prefijo xsl (versión renderizada)
                if "/" in doc:
                    doc = doc.split("/")[-1]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
                try:
                    xml_text = _get(url, as_json=False)
                except Exception:
                    continue
                for owner, shares, price in parse_form4(xml_text):
                    buyers[owner] = buyers.get(owner, 0) + shares * price

            if not buyers:
                continue
            total_usd = sum(buyers.values())
            n_buyers = len(buyers)

            if n_buyers >= 2:
                alerts.append({
                    "categoria":  "insider_cluster",
                    "severidad":  "alta",
                    "activo":     tk,
                    "titulo":     f"INSIDER CLUSTER: {n_buyers} insiders compraron {tk}",
                    "mensaje":    f"{n_buyers} insiders distintos compraron {tk} en los últimos "
                                  f"{days} días por un total de USD {total_usd:,.0f}. "
                                  f"Los cluster buys son la señal insider más predictiva. "
                                  f"Compradores: {', '.join(list(buyers.keys())[:4])}.",
                    "metricas":   {"n_insiders": n_buyers, "total_usd": round(total_usd, 0),
                                   "dias_ventana": days},
                    "sugerencia": "Señal de convicción interna fuerte. Revisar noticias y evaluar compra.",
                })
            elif total_usd >= 100_000:
                owner = list(buyers.keys())[0]
                alerts.append({
                    "categoria":  "insider_buy",
                    "severidad":  "media",
                    "activo":     tk,
                    "titulo":     f"INSIDER BUY: {owner} compró USD {total_usd:,.0f} de {tk}",
                    "mensaje":    f"{owner} compró USD {total_usd:,.0f} de {tk} en mercado abierto "
                                  f"(Form 4, código P) en los últimos {days} días.",
                    "metricas":   {"insider": owner, "total_usd": round(total_usd, 0)},
                    "sugerencia": "Compra individual significativa. Señal positiva secundaria.",
                })
        except Exception as e:
            if "404" not in str(e):
                print(f"  {tk}: {str(e)[:80]}")
    return alerts


# ── 2. 8-K — EVENTOS MATERIALES ─────────────────────────────
ITEM_DESC = {
    "1.01": "Acuerdo material", "1.02": "Término de acuerdo", "2.01": "Adquisición/venta de activos",
    "2.02": "Resultados", "2.05": "Costos de salida/restructuración", "3.01": "Delisting notice",
    "4.02": "Estados financieros NO confiables", "5.02": "Salida/nombramiento de ejecutivos",
    "7.01": "Reg FD", "8.01": "Otros eventos",
}
ITEMS_IMPORTANTES = {"1.01", "2.01", "2.05", "3.01", "4.02", "5.02"}


def check_8k(ciks: dict, days: int, cartera_tickers: set) -> list:
    """8-K de posiciones en cartera en los últimos N días."""
    alerts = []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    for tk, cik in ciks.items():
        if tk not in cartera_tickers:
            continue  # solo posiciones reales, para no spamear
        try:
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            items_list = recent.get("items", [""] * len(forms))
            for i, (f, d) in enumerate(zip(forms, dates)):
                if f != "8-K" or d < cutoff:
                    continue
                items = [x.strip() for x in (items_list[i] or "").split(",") if x.strip()]
                importantes = [x for x in items if x in ITEMS_IMPORTANTES]
                if not importantes:
                    continue  # 2.02/7.01/9.01 rutinarios se omiten
                desc = "; ".join(f"{x} ({ITEM_DESC.get(x, '?')})" for x in importantes)
                alerts.append({
                    "categoria":  "sec_8k",
                    "severidad":  "alta" if any(x in ("3.01", "4.02") for x in importantes) else "media",
                    "activo":     tk,
                    "titulo":     f"8-K de {tk}: {ITEM_DESC.get(importantes[0], 'evento material')}",
                    "mensaje":    f"{tk} presentó un 8-K el {d} con items: {desc}. "
                                  f"Revisar el filing en EDGAR para detalles.",
                    "metricas":   {"fecha_filing": d, "items": items},
                    "sugerencia": "Evento material en posición de cartera. Leer el 8-K antes de actuar.",
                })
                break  # max 1 alerta 8-K por ticker por corrida
        except Exception:
            pass
    return alerts


# ── 3. 13F — SMART MONEY ────────────────────────────────────
def _fetch_13f_holdings(cik: int, acc: str) -> dict:
    """Parsea el info table de un 13F-HR. → {nameOfIssuer: value_usd_miles}"""
    acc_clean = acc.replace("-", "")
    idx = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/index.json")
    info_file = None
    for f in idx.get("directory", {}).get("item", []):
        name = f.get("name", "").lower()
        if ("infotable" in name or "info_table" in name or "form13f" in name) and name.endswith(".xml"):
            info_file = f["name"]
            break
    if not info_file:
        return {}
    xml_text = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{info_file}",
                    as_json=False)
    holdings = {}
    try:
        # Namespace-agnostic parse
        xml_clean = re.sub(r'xmlns(:\w+)?="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)
        for it in root.iter():
            if it.tag.endswith("infoTable"):
                name = None
                value = 0
                for child in it.iter():
                    if child.tag.endswith("nameOfIssuer"):
                        name = (child.text or "").upper().strip()
                    elif child.tag.endswith("}value") or child.tag == "value":
                        try:
                            value = float(child.text or 0)
                        except ValueError:
                            pass
                if name:
                    holdings[name] = holdings.get(name, 0) + value
    except Exception:
        pass
    return holdings


def match_ticker(issuer_name: str) -> str:
    for alias, tk in NAME_ALIASES.items():
        if alias in issuer_name:
            return tk
    return None


def check_13f(days: int) -> list:
    """Detecta 13F-HR nuevos de los fondos smart money y diffea holdings."""
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
                continue  # sin filing nuevo en la ventana

            print(f"  13F nuevo de {fund['nombre']} ({f13[0][0]})")
            curr = _fetch_13f_holdings(cik, f13[0][1])
            prev = _fetch_13f_holdings(cik, f13[1][1]) if len(f13) > 1 else {}
            if not curr:
                continue

            for issuer, val in curr.items():
                tk = match_ticker(issuer)
                if not tk:
                    continue
                prev_val = prev.get(issuer, 0)
                if prev_val == 0:
                    tipo, cambio = "POSICIÓN NUEVA", ""
                elif val > prev_val * 1.5:
                    tipo = "AUMENTÓ"
                    cambio = f" ({(val/prev_val-1)*100:+.0f}% vs trimestre anterior)"
                else:
                    continue
                alerts.append({
                    "categoria":  "smart_money_13f",
                    "severidad":  "media",
                    "activo":     tk,
                    "titulo":     f"13F: {fund['pm']} — {tipo} {tk}",
                    "mensaje":    f"{fund['nombre']} ({fund['pm']}) reportó {tipo.lower()} en {tk}: "
                                  f"USD {val*1000:,.0f}{cambio}. Filing del {f13[0][0]} "
                                  f"(holdings al cierre del trimestre anterior).",
                    "metricas":   {"fondo": fund["nombre"], "pm": fund["pm"],
                                   "valor_usd": val * 1000, "tipo": tipo},
                    "sugerencia": "Smart money entró/aumentó. Dato con ~45 días de rezago — "
                                  "confirmar que la tesis siga vigente al precio actual.",
                })
        except Exception as e:
            print(f"  {fund.get('nombre', '?')}: {str(e)[:80]}")
    return alerts


# ── SAVE ────────────────────────────────────────────────────
def save_alerts(alerts: list) -> dict:
    if not alerts:
        return {"insertadas": 0, "errores": 0}
    sb = get_client()
    ins = err = 0
    pairs = set((a["categoria"], a["activo"]) for a in alerts)
    for cat, activo in pairs:
        try:
            sb.table("portfolio_alerts").update({"activo_alerta": False}) \
              .eq("activo_alerta", True).eq("categoria", cat).eq("activo", activo).execute()
        except Exception:
            pass
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
    parser.add_argument("--days", type=int, default=4,
                        help="Ventana de días para Form 4 y 8-K (default 4)")
    parser.add_argument("--days-13f", type=int, default=10,
                        help="Ventana para detectar 13F nuevos (default 10)")
    parser.add_argument("--skip-13f", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("EDGAR MONITOR v1 — Insiders + 8-K + Smart Money 13F")
    print("=" * 60)

    universe = build_universe()
    print(f"\nUniverso: {len(universe)} tickers")

    print("Resolviendo CIKs...")
    ciks = load_ticker_ciks(set(universe.keys()))
    print(f"  {len(ciks)} tickers con CIK")

    cartera_tickers = {tk for tk, src in universe.items() if src == "cartera"} | \
                      {tk for tk, src in universe.items() if src == "recurrente"}

    all_alerts = []

    print(f"\nForm 4 insider buys (últimos {args.days} días)...")
    a1 = check_insider_buys(ciks, args.days)
    all_alerts.extend(a1)
    print(f"  {len(a1)} alertas insider")

    print(f"8-K eventos materiales (últimos {args.days} días)...")
    a2 = check_8k(ciks, args.days, cartera_tickers)
    all_alerts.extend(a2)
    print(f"  {len(a2)} alertas 8-K")

    if not args.skip_13f:
        print(f"13F smart money (filings últimos {args.days_13f} días)...")
        a3 = check_13f(args.days_13f)
        all_alerts.extend(a3)
        print(f"  {len(a3)} alertas 13F")

    print(f"\nTotal: {len(all_alerts)} alertas EDGAR")
    for a in all_alerts[:12]:
        print(f"  [{a['severidad'].upper():6s}] {a['titulo']}")

    if args.dry_run:
        print("\nDRY RUN — no se guardó nada")
        return
    result = save_alerts(all_alerts)
    print(f"\nInsertadas: {result['insertadas']} | Errores: {result['errores']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
