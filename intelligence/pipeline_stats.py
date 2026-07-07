# ============================================================
# PIPELINE STATS v1 — Auto-auditoría: cada corrida escribe sus números
#
# Patrón (mismo que scouting-agent):
#   1. Cada corrida registra: filas nuevas, total tabla, duración, exit_ok
#   2. health_check compara contra el historial propio (~4 semanas)
#   3. Anomalías → sección 🩺 del email diario
#
# Modo WRAPPER (no toca la lógica de los loaders):
#   python -m intelligence.pipeline_stats \
#       --script load_santander --table santander_gastos -- \
#       python load_santander.py --days 14
#
#   Mide filas ANTES y DESPUÉS via count=exact (sin paginación),
#   corre el comando, registra todo y PROPAGA el exit code
#   (así el failure tracker del workflow sigue funcionando).
#
# Sin --table registra solo duración + exit_ok (ej: report_builder).
# CERO llamadas a APIs pagadas — aritmética sobre Supabase.
# ============================================================

import sys, time, subprocess, argparse, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from database.supabase_client import get_client


def count_rows(sb, table: str):
    """Total de filas via count=exact (HEAD request, inmune al límite de 1000)."""
    try:
        r = sb.table(table).select("*", count="exact", head=True).execute()
        return r.count
    except Exception as e:
        print(f"[pipeline_stats] no pude contar {table}: {str(e)[:80]}")
        return None


def record(sb, script: str, tabla: str, filas_nuevas, filas_totales,
           duracion: float, exit_ok: bool):
    try:
        sb.table("pipeline_stats").insert({
            "script": script,
            "tabla_destino": tabla,
            "filas_nuevas": filas_nuevas,
            "filas_totales_tabla": filas_totales,
            "duracion_seg": round(duracion, 1),
            "exit_ok": exit_ok,
        }).execute()
        print(f"[pipeline_stats] {script}: +{filas_nuevas if filas_nuevas is not None else '?'} filas "
              f"(total {filas_totales}), {duracion:.0f}s, exit_ok={exit_ok}")
    except Exception as e:
        # El registro de stats NUNCA debe romper el pipeline
        print(f"[pipeline_stats] warning: no pude registrar stats: {str(e)[:100]}")


def main():
    # Separar args propios del comando a envolver (después de "--")
    if "--" not in sys.argv:
        print("Uso: python -m intelligence.pipeline_stats --script NAME [--table TABLA] -- <comando>")
        sys.exit(2)
    split = sys.argv.index("--")
    own_args, cmd = sys.argv[1:split], sys.argv[split + 1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True, help="Nombre del paso (ej: load_santander)")
    parser.add_argument("--table", default=None, help="Tabla destino a medir (delta de filas)")
    args = parser.parse_args(own_args)

    if not cmd:
        print("Falta el comando después de --")
        sys.exit(2)

    sb = None
    before = None
    try:
        sb = get_client()
        if args.table:
            before = count_rows(sb, args.table)
    except Exception as e:
        print(f"[pipeline_stats] warning: sin conexión Supabase: {str(e)[:80]}")

    t0 = time.time()
    proc = subprocess.run(cmd)
    duracion = time.time() - t0
    exit_ok = proc.returncode == 0

    filas_nuevas = None
    after = None
    if sb is not None and args.table:
        after = count_rows(sb, args.table)
        if before is not None and after is not None:
            filas_nuevas = after - before

    if sb is not None:
        record(sb, args.script, args.table, filas_nuevas, after, duracion, exit_ok)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
