# ============================================================
# MAC NOTIFICATION READER
#
# Lee las notificaciones de Santander que llegan al Mac (vía
# Continuity desde el iPhone) directamente desde la SQLite de
# macOS, las parsea, y las envía a la Edge Function que las
# inserta en santander_gastos.
#
# Funciona en macOS 13+ (Ventura+). Requiere "Full Disk Access"
# para Terminal (o el binario que lo ejecuta).
#
# Setup:
#   1. System Settings → Privacy & Security → Full Disk Access
#      → Agregar Terminal.app
#   2. Variable de entorno:
#        export NOTIFICATION_INGEST_URL=...
#        export NOTIFICATION_TOKEN=...
#   3. Probar: python -m intelligence.mac_notification_reader --since 24h
#
# Para automatizar: usar launchd para correr cada 5 min.
# ============================================================

import os, sys, sqlite3, json, plistlib, argparse, hashlib
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")

import requests
from dotenv import load_dotenv
load_dotenv()

INGEST_URL = os.getenv("NOTIFICATION_INGEST_URL")
TOKEN      = os.getenv("NOTIFICATION_TOKEN")

# macOS notification center DB
DB_PATH = Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db"

# Filtros: bundles que nos interesan
SANTANDER_BUNDLE_HINTS = [
    "santander",       # cubre la mayoría
    "cl.santander",
    "com.santander",
]


def find_db() -> Path:
    if DB_PATH.exists():
        return DB_PATH
    # Fallbacks en macOS más viejos
    alt = Path.home() / "Library/Application Support/NotificationCenter"
    for p in alt.glob("*.db"):
        return p
    raise FileNotFoundError(
        f"No se encontró la BD de notificaciones en {DB_PATH}. "
        "Asegúrate de tener Full Disk Access para tu terminal."
    )


def read_notifications(since: datetime) -> list[dict]:
    """
    Lee la SQLite del Notification Center y retorna notificaciones de Santander.
    El schema cambia entre versiones de macOS, hacemos parsing tolerante.
    """
    db = find_db()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # En macOS Ventura/Sonoma el schema es:
    #   record: rec_id, app_id, uuid, data (BLOB plist), delivered_date, ...
    #   app:    app_id, identifier
    try:
        rows = conn.execute("""
            SELECT r.rec_id, r.delivered_date, r.data, a.identifier
            FROM record r
            JOIN app a ON r.app_id = a.app_id
            WHERE r.delivered_date IS NOT NULL
        """).fetchall()
    except sqlite3.OperationalError as e:
        print(f"❌ No se pudo leer la tabla 'record': {e}")
        print("   Probablemente falta Full Disk Access.")
        return []

    # delivered_date es Mac absolute time (segundos desde 2001-01-01 UTC)
    APPLE_EPOCH = datetime(2001, 1, 1)

    results = []
    for r in rows:
        bundle = (r["identifier"] or "").lower()
        if not any(h in bundle for h in SANTANDER_BUNDLE_HINTS):
            continue

        # Decodificar fecha
        try:
            fecha = APPLE_EPOCH + timedelta(seconds=float(r["delivered_date"]))
        except Exception:
            continue

        if fecha < since:
            continue

        # Parse plist data
        try:
            plist = plistlib.loads(r["data"])
        except Exception:
            continue

        # plist típicamente tiene: app, req (NSDictionary con title, subtitle, body, etc.)
        req = plist.get("req", {}) if isinstance(plist, dict) else {}
        titulo = req.get("titl") or req.get("title") or ""
        subt   = req.get("subt") or req.get("subtitle") or ""
        body   = req.get("body") or ""

        # Combinar texto disponible
        full_text = " ".join(str(x) for x in [titulo, subt, body] if x).strip()
        if not full_text:
            continue

        results.append({
            "fecha":    fecha.isoformat(),
            "bundle":   bundle,
            "text":     full_text,
            "rec_id":   r["rec_id"],
            "fingerprint": hashlib.sha256(f"{r['rec_id']}|{full_text}".encode()).hexdigest()[:32],
        })

    return results


def already_sent(fingerprint: str, cache_file: Path) -> bool:
    """Evita reenviar la misma notificación si el script corre varias veces."""
    if not cache_file.exists():
        return False
    sent = cache_file.read_text().splitlines()
    return fingerprint in sent


def mark_sent(fingerprint: str, cache_file: Path):
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("a") as f:
        f.write(fingerprint + "\n")


def send_to_supabase(text: str) -> dict:
    if not INGEST_URL or not TOKEN:
        return {"ok": False, "error": "missing_env_vars"}
    try:
        r = requests.post(
            INGEST_URL,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
            json={"text": text},
            timeout=10,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def parse_since(s: str) -> datetime:
    """Parse '24h', '60m', '7d' → datetime."""
    now = datetime.now()
    if s.endswith("h"):
        return now - timedelta(hours=int(s[:-1]))
    if s.endswith("m"):
        return now - timedelta(minutes=int(s[:-1]))
    if s.endswith("d"):
        return now - timedelta(days=int(s[:-1]))
    return now - timedelta(hours=24)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="1h",
                        help="Periodo a leer (ej 30m, 1h, 24h, 7d). Default: 1h")
    parser.add_argument("--dry-run", action="store_true",
                        help="No envía a Supabase, solo muestra")
    args = parser.parse_args()

    print("=" * 60)
    print("📱 Mac Notification Reader — Santander")
    print("=" * 60)

    since = parse_since(args.since)
    print(f"⏰ Leyendo notificaciones desde {since.strftime('%Y-%m-%d %H:%M')}")

    notifs = read_notifications(since)
    print(f"📋 Encontradas: {len(notifs)} notificaciones Santander\n")

    if not notifs:
        return

    cache = Path.home() / ".financial_dashboard/notif_cache.txt"
    sent_ok = sent_dup = sent_err = 0

    for n in notifs:
        if already_sent(n["fingerprint"], cache):
            sent_dup += 1
            continue

        print(f"  📨 [{n['fecha'][:16]}] {n['text'][:80]}")
        if args.dry_run:
            sent_ok += 1
            continue

        resp = send_to_supabase(n["text"])
        if resp.get("ok"):
            print(f"     ✅ enviado (gasto_id={resp.get('gasto_id')}, parsed={resp.get('parsed')})")
            mark_sent(n["fingerprint"], cache)
            sent_ok += 1
        else:
            print(f"     ❌ {resp.get('error')}: {resp.get('detail','')}")
            sent_err += 1

    print(f"\n{'='*60}")
    print(f"  ✅ Enviadas:    {sent_ok}")
    print(f"  ⏭  Ya enviadas: {sent_dup}")
    print(f"  ❌ Errores:     {sent_err}")
    if args.dry_run:
        print(f"\n  ⚠️ DRY RUN")


if __name__ == "__main__":
    main()
