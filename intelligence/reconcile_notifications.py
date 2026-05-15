# ============================================================
# RECONCILIACIÓN DE NOTIFICACIONES vs PDF
#
# Cuando llega el PDF mensual de Santander con los gastos reales,
# este script:
#   1. Busca entradas con fuente='notification_iphone' aún no
#      reconciliadas.
#   2. Para cada una, intenta matchear con una entrada del PDF
#      por (fecha ±3 días, monto exacto, merchant similar).
#   3. Si encuentra match → marca la notificación como reconciliada
#      y BORRA la entrada preliminar de notification_iphone
#      (el PDF es la fuente autoritativa).
#   4. Si no hay match después de 14 días, la entrada queda como
#      legítima (la TX puede aparecer en el siguiente ciclo de PDF).
#
# Uso:
#   python -m intelligence.reconcile_notifications
#   python -m intelligence.reconcile_notifications --dry-run
# ============================================================

import sys, argparse, difflib
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
from database.supabase_client import get_client


def normalize_merchant(s: str) -> str:
    """Normaliza nombre de merchant para comparar."""
    if not s:
        return ""
    s = s.upper().strip()
    # Remover sufijos comunes
    for suf in ["SANTIAGO", "CHILE", "SPA", "S.A.", "SA", "LTDA", "LIMITADA"]:
        s = s.replace(suf, "")
    # Remover caracteres no alfanuméricos
    s = "".join(c for c in s if c.isalnum() or c.isspace())
    s = " ".join(s.split())
    return s


def merchants_match(a: str, b: str, threshold: float = 0.65) -> bool:
    """Fuzzy match entre dos merchant names."""
    na, nb = normalize_merchant(a), normalize_merchant(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    return ratio >= threshold


def reconcile(dry_run: bool = False):
    sb = get_client()

    # 1. Notificaciones pendientes (no reconciliadas) y su gasto preliminar
    notifs = (sb.table("notification_inbox")
                .select("id, parsed_monto, parsed_descripcion, parsed_moneda, fecha_recibido, gasto_id, reconciliado")
                .eq("reconciliado", False)
                .eq("procesado", True)
                .not_.is_("gasto_id", "null")
                .execute())

    if not notifs.data:
        print("✅ No hay notificaciones pendientes de reconciliar.")
        return

    print(f"📋 {len(notifs.data)} notificaciones pendientes de reconciliar\n")

    # 2. Cargar PDF entries recientes (fuente != notification_iphone)
    # Buscar todos los gastos de los últimos 60 días que NO vengan de notification
    cutoff = (datetime.now() - timedelta(days=60)).date().isoformat()
    pdf_q = (sb.table("santander_gastos")
              .select("id, fecha, descripcion, monto, moneda, fuente")
              .gte("fecha", cutoff)
              .execute())

    df_pdf = pd.DataFrame(pdf_q.data)
    if df_pdf.empty:
        print("⚠️ No hay gastos PDF para comparar.")
        return

    df_pdf = df_pdf[(df_pdf["fuente"].isna()) | (df_pdf["fuente"] != "notification_iphone")]
    print(f"📄 {len(df_pdf)} gastos PDF candidatos para match (últimos 60d)\n")

    # 3. Matching
    matched = 0
    deleted = 0
    keep_too_old = 0  # notificaciones muy viejas sin match

    for n in notifs.data:
        monto = float(n["parsed_monto"] or 0)
        desc  = n["parsed_descripcion"] or ""
        moneda = n["parsed_moneda"] or "CLP"
        fecha_n = pd.to_datetime(n["fecha_recibido"]).date()
        notif_id = n["id"]
        gasto_id = n["gasto_id"]

        # Match en df_pdf:
        # - misma moneda
        # - monto exacto (±$1 CLP por redondeo)
        # - fecha ±3 días
        candidates = df_pdf[
            (df_pdf["moneda"] == moneda) &
            (abs(pd.to_numeric(df_pdf["monto"], errors="coerce") - monto) <= 1)
        ].copy()

        if candidates.empty:
            # Si pasaron > 14 días sin match, no insistir
            days_old = (datetime.now().date() - fecha_n).days
            if days_old > 14:
                keep_too_old += 1
            continue

        candidates["fecha_dt"] = pd.to_datetime(candidates["fecha"]).dt.date
        candidates["diff_dias"] = candidates["fecha_dt"].apply(lambda f: abs((f - fecha_n).days))
        candidates = candidates[candidates["diff_dias"] <= 3]

        if candidates.empty:
            continue

        # Filtrar por merchant similar
        candidates["match_merch"] = candidates["descripcion"].apply(lambda d: merchants_match(desc, d))
        winners = candidates[candidates["match_merch"]].sort_values("diff_dias")

        if winners.empty:
            # Sin coincidencia de merchant — podría ser otro gasto del mismo monto
            continue

        winner = winners.iloc[0]
        print(f"✅ MATCH: notif#{notif_id} '{desc[:30]}' (${monto:,.0f} {moneda}) "
              f"↔ PDF#{winner['id']} '{winner['descripcion'][:30]}'  Δ{winner['diff_dias']}d")

        if dry_run:
            matched += 1
            continue

        try:
            # Marcar notificación como reconciliada
            sb.table("notification_inbox").update({
                "reconciliado": True,
                "gasto_id": int(winner["id"]),  # apuntar al gasto autoritativo
            }).eq("id", notif_id).execute()

            # Borrar gasto preliminar (fuente='notification_iphone')
            sb.table("santander_gastos").delete().eq("id", gasto_id).execute()
            matched += 1
            deleted += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print(f"\n{'='*60}")
    print(f"  ✅ Matches:                   {matched}")
    print(f"  🗑  Gastos preliminares borrados: {deleted}")
    print(f"  ⏳ Notificaciones >14d sin match: {keep_too_old}")
    if dry_run:
        print(f"\n  ⚠️ DRY RUN — no se aplicó nada")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra qué se haría, sin escribir cambios")
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 RECONCILIACIÓN NOTIFICACIONES iPhone vs PDF Santander")
    print("=" * 60)
    reconcile(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
