# ============================================================
# UPDATE CARTERA_ACTUAL
#
# Sincroniza cartera_actual con:
#   1. Base: snapshot manual del 2026-04-30 (vía load_portfolio.py)
#   2. Movimientos posteriores de racional_transacciones (compras + ventas)
#   3. Compras programadas Buda (crypto)
#   4. Precios actuales vía yfinance
#
# Uso:
#   python update_cartera.py            → actualización completa
#   python update_cartera.py --no-prices → solo cantidades (sin yfinance)
#   python update_cartera.py --dry-run  → muestra cambios sin escribir
# ============================================================

import sys, argparse, warnings
from datetime import datetime, date
from collections import defaultdict
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
from database.supabase_client import get_client


# Fecha del último snapshot manual (de load_portfolio.py)
SNAPSHOT_DATE = "2026-04-30"


def fetch_all(table: str, page_size: int = 1000) -> list[dict]:
    sb = get_client()
    all_rows, page = [], 0
    while True:
        r = sb.table(table).select("*").range(page*page_size, page*page_size + page_size - 1).execute()
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows


def load_cartera_df() -> pd.DataFrame:
    df = pd.DataFrame(fetch_all("cartera_actual"))
    for col in ["cantidad", "precio_compra", "precio_actual"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_racional_post_snapshot() -> pd.DataFrame:
    """Transacciones Racional posteriores al snapshot."""
    sb = get_client()
    r = (sb.table("racional_transacciones")
           .select("*")
           .gt("fecha", SNAPSHOT_DATE)
           .execute())
    df = pd.DataFrame(r.data)
    if df.empty:
        return df
    for c in ["acciones", "precio_usd", "monto_usd", "monto_clp"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def load_buda_post_snapshot() -> pd.DataFrame:
    """Compras crypto Buda posteriores al snapshot."""
    sb = get_client()
    r = (sb.table("buda_crypto")
           .select("*")
           .gt("fecha", SNAPSHOT_DATE)
           .execute())
    df = pd.DataFrame(r.data)
    if df.empty:
        return df
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    return df


def apply_racional_diffs(df_cartera: pd.DataFrame, df_rac: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Aplica compras y ventas de Racional sobre cartera. Retorna df modificado + log."""
    if df_rac.empty:
        return df_cartera, []

    df_c = df_cartera.copy().set_index("ticker")
    log = []

    # Solo internacional (las nacionales son al "Portafolio Acciones Chilenas" agregado;
    # esas se manejan aparte porque no especifican qué stocks chilenos compraron)
    intl = df_rac[df_rac["mercado"] == "internacional"].copy()

    # Compras: agregar acciones
    compras = intl[intl["tipo"] == "compra"]
    for _, row in compras.iterrows():
        tk = row["ticker"]
        qty = row.get("acciones") or 0
        if tk in df_c.index:
            old_qty = df_c.at[tk, "cantidad"]
            new_qty = (old_qty or 0) + qty
            df_c.at[tk, "cantidad"] = new_qty
            log.append(f"  ➕ {tk}: {old_qty:.4f} + {qty:.4f} = {new_qty:.4f}  ({row['fecha'].date()})")
        else:
            # Nuevo ticker que no estaba en snapshot — agregar
            new_row = {
                "ticker": tk,
                "empresa": row.get("empresa", tk),
                "mercado": "internacional",
                "cantidad": qty,
                "precio_compra": row.get("precio_usd") or 0,
                "precio_actual": row.get("precio_usd") or 0,
                "moneda": "USD",
                "fecha_actualizacion": str(date.today()),
            }
            df_c.loc[tk] = pd.Series(new_row)
            log.append(f"  🆕 {tk}: nuevo ticker, qty={qty:.4f}")

    # Ventas: restar acciones
    ventas = intl[intl["tipo"] == "venta"]
    for _, row in ventas.iterrows():
        tk = row["ticker"]
        qty = row.get("acciones") or 0
        if tk in df_c.index:
            old_qty = df_c.at[tk, "cantidad"]
            new_qty = max((old_qty or 0) - qty, 0)
            df_c.at[tk, "cantidad"] = new_qty
            log.append(f"  ➖ {tk}: {old_qty:.4f} - {qty:.4f} = {new_qty:.4f}  ({row['fecha'].date()})")
            if new_qty == 0:
                log.append(f"    ⚠️ {tk} llegó a 0 — se eliminará de cartera")
        else:
            log.append(f"  ⚠️ Venta de {tk} pero no estaba en cartera (ignorado)")

    # Eliminar posiciones con cantidad 0
    df_c = df_c[df_c["cantidad"] > 0]

    return df_c.reset_index(), log


def apply_buda_diffs(df_cartera: pd.DataFrame, df_buda: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Suma compras de crypto Buda a cartera_actual."""
    if df_buda.empty:
        return df_cartera, []

    df_c = df_cartera.copy().set_index("ticker")
    log = []

    # Agrupar por activo
    grp = df_buda.groupby("activo")["cantidad"].sum()
    for activo, qty in grp.items():
        if activo in df_c.index:
            old = df_c.at[activo, "cantidad"]
            df_c.at[activo, "cantidad"] = (old or 0) + qty
            log.append(f"  🪙 {activo}: {old:.8f} + {qty:.8f}")
        else:
            log.append(f"  ⚠️ Compra Buda {activo} pero no está en cartera (ignorado)")

    return df_c.reset_index(), log


def update_prices(df_cartera: pd.DataFrame) -> pd.DataFrame:
    """Refresca precio_actual con yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        print("  ⚠️ yfinance no disponible, sin actualizar precios")
        return df_cartera

    df = df_cartera.copy()
    # Mapeo ticker → ticker yfinance (con .SN para Chile)
    yf_map = {}
    for _, row in df.iterrows():
        tk = row["ticker"]
        if not tk or tk == "PORTFOLIO_CL":
            continue
        if row.get("mercado") == "nacional":
            yf_map[tk] = f"{tk}.SN"
        elif row.get("mercado") == "crypto":
            yf_map[tk] = f"{tk}-USD"
        else:
            yf_map[tk] = tk

    if not yf_map:
        return df

    yf_tickers = list(yf_map.values())
    print(f"  📡 Bajando precios de {len(yf_tickers)} tickers (yfinance)…")
    try:
        data = yf.download(yf_tickers, period="5d", interval="1d",
                           auto_adjust=True, progress=False, group_by="ticker")
        if data.empty:
            print("  ⚠️ yfinance retornó vacío")
            return df

        # Extraer último Close
        precios = {}
        for tk, tk_yf in yf_map.items():
            try:
                if len(yf_tickers) == 1:
                    serie = data["Close"]
                else:
                    serie = data[tk_yf]["Close"] if (tk_yf in data.columns.get_level_values(0)) else data["Close"][tk_yf]
                ultimo = serie.dropna().iloc[-1]
                precios[tk] = float(ultimo)
            except Exception:
                continue

        # Aplicar
        updated = 0
        for idx, row in df.iterrows():
            tk = row["ticker"]
            if tk in precios:
                df.at[idx, "precio_actual"] = precios[tk]
                updated += 1
        print(f"  ✅ {updated}/{len(yf_map)} precios actualizados")
    except Exception as e:
        print(f"  ⚠️ Error yfinance: {e}")

    # Actualizar fecha
    df["fecha_actualizacion"] = str(date.today())
    return df


def write_cartera(df: pd.DataFrame):
    """Reescribe cartera_actual con el df actualizado."""
    sb = get_client()
    # Borrar tabla actual
    sb.table("cartera_actual").delete().neq("id", 0).execute()
    # Insertar nueva
    records = df.drop(columns=["id", "created_at"], errors="ignore").to_dict("records")
    # Limpiar NaN
    for r in records:
        for k, v in list(r.items()):
            if pd.isna(v):
                r[k] = None
    sb.table("cartera_actual").insert(records).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-prices", action="store_true",
                        help="No actualizar precios (saltar yfinance)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra cambios sin escribir a Supabase")
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 UPDATE CARTERA_ACTUAL")
    print("=" * 60)

    print(f"\n📌 Snapshot base: {SNAPSHOT_DATE}")
    print("📊 Cargando cartera actual...")
    df_cartera = load_cartera_df()
    print(f"   {len(df_cartera)} posiciones")

    print("\n📊 Cargando transacciones Racional posteriores...")
    df_rac = load_racional_post_snapshot()
    print(f"   {len(df_rac)} transacciones (compras + ventas)")

    print("\n📊 Cargando compras Buda posteriores...")
    df_buda = load_buda_post_snapshot()
    print(f"   {len(df_buda)} compras")

    print("\n▶ Aplicando diffs Racional internacional...")
    df_cartera, log_rac = apply_racional_diffs(df_cartera, df_rac)
    for line in log_rac:
        print(line)

    print("\n▶ Aplicando compras Buda...")
    df_cartera, log_buda = apply_buda_diffs(df_cartera, df_buda)
    for line in log_buda:
        print(line)

    if not args.no_prices:
        print("\n▶ Refrescando precios (yfinance)...")
        df_cartera = update_prices(df_cartera)

    if args.dry_run:
        print("\n⚠️ DRY RUN — no se escribió a Supabase")
        print(f"\nCartera resultante: {len(df_cartera)} posiciones")
    else:
        print(f"\n▶ Escribiendo {len(df_cartera)} posiciones a Supabase...")
        write_cartera(df_cartera)
        print("✅ cartera_actual actualizada")

    print("=" * 60)


if __name__ == "__main__":
    main()
