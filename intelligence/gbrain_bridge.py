# ============================================================
# GBRAIN BRIDGE v1 — Conecta el brain personal con el sistema
#
# SOLO CORRE LOCAL (el brain vive en este Mac). Se invoca desde
# run_weekly_update.sh (LaunchAgent diario 7am).
#
# Dirección 1 (brain → sistema):
#   Lee newsletters nuevas de GBrain (Revolution, Chamath, etc.),
#   extrae menciones de tickers del universo y las inserta en
#   market_news con fuente="GBrain". Research curado por humanos
#   que ya estás leyendo — ahora también alimenta las alertas.
#
# Dirección 2 (sistema → brain):
#   Escribe el resumen diario de alertas activas en la página
#   finanzas/alertas-sistema del brain, para que el advisor de
#   GBrain tenga memoria de qué señales hubo y cuándo.
#
# Uso:
#   python -m intelligence.gbrain_bridge
#   python -m intelligence.gbrain_bridge --dry-run --days 3
# ============================================================

import sys, os, re, argparse, subprocess, warnings, tempfile
from datetime import date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import yaml
from pathlib import Path
from database.supabase_client import get_client

WATCHLIST_PATH = Path(__file__).parent / "config" / "watchlist.yaml"
PROFILE_PATH = Path(__file__).parent / "config" / "investor_profile.yaml"
GBRAIN = os.path.expanduser("~/.bun/bin/gbrain")

# Tickers cortos/ambiguos: solo cuentan con $TICK o (TICK)
AMBIGUOS = {"BE", "MP", "MU", "VT", "ILF", "CAP", "NU", "UNH", "ARES", "CHILE"}

# Nombres de empresa → ticker (para cuando la newsletter no usa el ticker)
NAME_HINTS = {
    "nvidia": "NVDA", "microsoft": "MSFT", "alphabet": "GOOGL", "google": "GOOGL",
    "amazon": "AMZN", "mercadolibre": "MELI", "mercado libre": "MELI", "nubank": "NU",
    "taiwan semiconductor": "TSM", "tsmc": "TSM", "broadcom": "AVGO", "marvell": "MRVL",
    "uber": "UBER", "eli lilly": "LLY", "unitedhealth": "UNH", "coreweave": "CRWV",
    "nebius": "NBIS", "oklo": "OKLO", "ionq": "IONQ", "cameco": "CCJ",
    "kratos": "KTOS", "rocket lab": "RKLB", "cerebras": "CBRS", "robinhood": "HOOD",
    "palo alto networks": "PANW", "micron": "MU", "asml": "ASML", "qualcomm": "QCOM",
    "symbotic": "SYM", "bloom energy": "BE", "mp materials": "MP",
}


def run_gbrain(*args) -> str:
    try:
        r = subprocess.run([GBRAIN, *args], capture_output=True, text=True, timeout=120)
        return r.stdout
    except Exception as e:
        print(f"  gbrain error: {str(e)[:100]}")
        return ""


def build_universe() -> set:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        wl = yaml.safe_load(f)
    with open(PROFILE_PATH, encoding="utf-8") as f:
        prof = yaml.safe_load(f)
    tks = set()
    for r in wl.get("recurrente", []):
        tks.add(r["ticker"])
    for tier in ("tier1", "tier2", "tier3"):
        for i in wl.get("watchlist", {}).get(tier, []):
            tks.add(i["ticker"])
    for vert in prof.get("verticales", {}).values():
        tks.update(vert.get("tickers", {}).keys())
    tks.update(prof.get("core", {}).get("tickers", []))
    tks.update(prof.get("diversificadores_renta_fija", {}).get("tickers", {}).keys())
    return tks


def extract_tickers(text: str, universe: set) -> list:
    """Menciones de tickers del universo en el texto (con guardas anti-falso-positivo)."""
    found = set()
    upper = text.upper()
    for tk in universe:
        if tk in AMBIGUOS:
            # Solo $TICK, (TICK) o "TICK:" cuentan para ambiguos
            if re.search(rf"[\$\(]{tk}[\)\s:,.]", upper) or f"({tk})" in upper:
                found.add(tk)
        else:
            if re.search(rf"\b{re.escape(tk)}\b", upper):
                found.add(tk)
    lower = text.lower()
    for name, tk in NAME_HINTS.items():
        if name in lower and tk in universe:
            found.add(tk)
    return sorted(found)


# ── DIRECCIÓN 1: newsletters → market_news ──────────────────
def sync_newsletters(days: int, dry_run: bool) -> int:
    universe = build_universe()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    listing = run_gbrain("list", "-n", "100")
    if not listing:
        print("  No se pudo listar páginas del brain.")
        return 0

    candidates = []
    for line in listing.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        slug, ptype, updated, title = parts[0], parts[1], parts[2], parts[3]
        if slug.startswith("newsletters/") and updated >= cutoff:
            candidates.append((slug, updated, title))

    print(f"  {len(candidates)} newsletters nuevas en el brain (últimos {days} días)")
    if not candidates:
        return 0

    sb = get_client()
    inserted = 0
    for slug, updated, title in candidates:
        url = f"gbrain://{slug}"
        # Dedupe por URL
        try:
            exists = sb.table("market_news").select("id").eq("url", url).limit(1).execute()
            if exists.data:
                continue
        except Exception:
            pass

        content = run_gbrain("get", slug)
        if not content:
            continue
        tickers = extract_tickers(content, universe)
        # Relevancia: base 30 si es financiera, +12 por ticker del universo
        es_financiera = any(k in slug for k in ("revolution", "chamath", "macro", "invers"))
        relevancia = (30 if es_financiera else 15) + 12 * len(tickers)
        if not tickers and not es_financiera:
            continue  # newsletters de producto/estrategia sin tickers no aportan al detector

        row = {
            "titulo": f"[Newsletter] {title}",
            "resumen": content[:400].replace("\n", " "),
            "url": url,
            "fuente": "GBrain Newsletter",
            "fecha_noticia": updated,
            "tickers_mencionados": tickers,
            "sectores_mencionados": [],
            "relevancia_preliminar": min(relevancia, 90),
            "procesado_ai": False,
        }
        if dry_run:
            print(f"    [DRY] {slug} → tickers: {tickers} (rel {row['relevancia_preliminar']})")
            inserted += 1
            continue
        try:
            sb.table("market_news").insert(row).execute()
            inserted += 1
            print(f"    + {slug} → {tickers}")
        except Exception as e:
            print(f"    {slug}: {str(e)[:80]}")
    return inserted


# ── DIRECCIÓN 2: alertas → brain ────────────────────────────
def push_alerts_to_brain(dry_run: bool) -> bool:
    sb = get_client()
    try:
        r = (sb.table("portfolio_alerts").select("*")
             .eq("activo_alerta", True)
             .neq("categoria", "daily_brief")
             .order("fecha_alerta", desc=True)
             .limit(60).execute())
        alerts = r.data
    except Exception as e:
        print(f"  Error leyendo alertas: {e}")
        return False

    sev_order = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "info": 4}
    alerts.sort(key=lambda a: sev_order.get((a.get("severidad") or "info"), 9))
    hoy = date.today().isoformat()

    lines = [
        f"# Alertas del Sistema de Inversiones — {hoy}",
        "",
        "Página actualizada diariamente por el Financial Dashboard "
        "([[finanzas/watchlist]], [[finanzas/snapshot-semanal]]).",
        "",
        f"**{len(alerts)} alertas activas.** Top 20 por severidad:",
        "",
    ]
    for a in alerts[:20]:
        sev = (a.get("severidad") or "info").upper()
        lines.append(f"- **[{sev}] {a.get('titulo', '?')}** — {a.get('mensaje', '')[:200]}")
    lines += ["", "## Cómo leer esto",
              "- `oportunidad_dip`/`oportunidad_rsi2`: señales de compra técnicas (z-score de vol propia)",
              "- `insider_cluster`/`insider_buy`/`smart_money_13f`: señales informacionales SEC EDGAR",
              "- `venta_*`: concentración, trailing 2σ, evaluar al duplicar",
              "- `earnings_proximos`: decidir ANTES del print",
              ""]
    md = "\n".join(lines)

    if dry_run:
        print(f"  [DRY] Página finanzas/alertas-sistema ({len(md)} chars, {len(alerts)} alertas)")
        return True

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md)
        tmp = f.name
    try:
        subprocess.run([GBRAIN, "put", "finanzas/alertas-sistema"],
                       stdin=open(tmp), capture_output=True, text=True, timeout=120)
        print(f"  Página finanzas/alertas-sistema actualizada ({len(alerts)} alertas)")
        return True
    except Exception as e:
        print(f"  Error escribiendo al brain: {str(e)[:100]}")
        return False
    finally:
        os.unlink(tmp)


# ── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=2,
                        help="Ventana de newsletters a sincronizar (default 2)")
    args = parser.parse_args()

    print("=" * 60)
    print("GBRAIN BRIDGE v1 — brain ↔ sistema de alertas")
    print("=" * 60)

    if not os.path.exists(GBRAIN):
        print(f"gbrain CLI no encontrado en {GBRAIN}. Este script solo corre local.")
        sys.exit(0)

    print("\n[1/2] Newsletters del brain → market_news...")
    n = sync_newsletters(args.days, args.dry_run)
    print(f"  {n} newsletters sincronizadas")

    print("\n[2/2] Alertas activas → brain (finanzas/alertas-sistema)...")
    push_alerts_to_brain(args.dry_run)

    print("=" * 60)


if __name__ == "__main__":
    main()
