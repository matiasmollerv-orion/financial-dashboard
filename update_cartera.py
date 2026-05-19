# ============================================================
# UPDATE CARTERA_ACTUAL — IDEMPOTENTE
#
# Reconstruye cartera_actual desde CERO en cada corrida:
#   1. Lee snapshot inmutable de cartera_base.py
#   2. Aplica TODAS las transacciones racional_transacciones
#      posteriores a SNAPSHOT_DATE (compras + ventas)
#   3. Aplica TODAS las compras buda_crypto posteriores
#   4. Refresca precios desde yfinance
#   5. DELETE + INSERT en cartera_actual
#
# Idempotente: correr 1, 5 o 100 veces da el mismo resultado.
#
# Uso:
#   python update_cartera.py            → completo
#   python update_cartera.py --no-prices → sin yfinance
#   python update_cartera.py --dry-run  → no escribe
# ============================================================

import sys, argparse, warnings
from datetime import date
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
from database.supabase_client import get_client
from cartera_base import get_base, SNAPSHOT_DATE


def fetch_all(table: str, filter_col: str = None, filter_val=None,
              page_size: int = 1000) -> list[dict]:
    sb = get_client()
    all_rows, page = [], 0
    while True:
        q = sb.table(table).select("*").range(page*page_size, page*page_size + page_size - 1)
        if filter_col and filter_val is not None:
            q = q.gt(filter_col, filter_val)
        r = q.execute()
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return all_rows


def apply_racional(df_cart: pd.DataFrame, df_rac: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Aplica compras/ventas Racional internacional sobre cartera."""
    log = []
    if df_rac.empty:
        return df_cart, log

    df_c = df_cart.copy().set_index("ticker")
    intl = df_rac[df_rac["mercado"] == "internacional"].copy()
    intl["acciones"] = pd.to_numeric(intl["acciones"], errors="coerce")
    intl["precio_usd"] = pd.to_numeric(intl["precio_usd"], errors="coerce")

    for _, row in intl[intl["tipo"] == "compra"].iterrows():
        tk = row["ticker"]
        qty = float(row.get("acciones") or 0)
        if qty <= 0:
            continue
        if tk in df_c.index:
            df_c.at[tk, "cantidad"] = (df_c.at[tk, "cantidad"] or 0) + qty
        else:
            df_c.loc[tk] = pd.Series({
                "empresa": row.get("empresa", tk),
                "mercado": "internacional",
                "cantidad": qty,
                "precio_compra": row.get("precio_usd") or 0,
                "precio_actual": row.get("precio_usd") or 0,
                "moneda": "USD",
                "fecha_actualizacion": str(date.today()),
            })
            log.append(f"  🆕 {tk}: ticker nuevo")

    for _, row in intl[intl["tipo"] == "venta"].iterrows():
        tk = row["ticker"]
        qty = float(row.get("acciones") or 0)
        if qty <= 0:
            continue
        if tk in df_c.index:
            df_c.at[tk, "cantidad"] = max((df_c.at[tk, "cantidad"] or 0) - qty, 0)

    df_c = df_c[df_c["cantidad"] > 0]
    log.append(f"  ✅ Aplicadas {len(intl)} transacciones internacionales")
    return df_c.reset_index(), log


def apply_buda(df_cart: pd.DataFrame, df_buda: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Suma compras crypto Buda."""
    log = []
    if df_buda.empty:
        return df_cart, log

    df_c = df_cart.copy().set_index("ticker")
    df_buda["cantidad"] = pd.to_numeric(df_buda["cantidad"], errors="coerce")
    grp = df_buda.groupby("activo")["cantidad"].sum()

    for activo, qty in grp.items():
        if activo in df_c.index:
            df_c.at[activo, "cantidad"] = (df_c.at[activo, "cantidad"] or 0) + float(qty)
        else:
            df_c.loc[activo] = pd.Series({
                "empresa": activo,
                "mercado": "crypto",
                "cantidad": float(qty),
                "precio_compra": 0,
                "precio_actual": 0,
                "moneda": "USD",
                "fecha_actualizacion": str(date.today()),
            })

    log.append(f"  ✅ Aplicadas {len(grp)} acumulaciones crypto Buda")
    return df_c.reset_index(), log


def update_prices(df_cart: pd.DataFrame) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError:
        print("  ⚠️ yfinance no disponible")
        return df_cart

    df = df_cart.copy()
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
    print(f"  📡 Bajando precios de {len(yf_tickers)} tickers…")
    try:
        data = yf.download(yf_tickers, period="5d", interval="1d",
                           auto_adjust=True, progress=False, group_by="ticker")
        if data.empty:
            print("  ⚠️ yfinance retornó vacío")
            return df

        precios = {}
        for tk, tk_yf in yf_map.items():
            try:
                if len(yf_tickers) == 1:
                    serie = data["Close"]
                else:
                    if tk_yf in data.columns.get_level_values(0):
                        serie = data[tk_yf]["Close"]
                    else:
                        serie = data["Close"][tk_yf]
                ultimo = serie.dropna().iloc[-1]
                precios[tk] = float(ultimo)
            except Exception:
                continue

        updated = 0
        for idx, row in df.iterrows():
            tk = row["ticker"]
            if tk in precios:
                df.at[idx, "precio_actual"] = precios[tk]
                updated += 1
        print(f"  ✅ {updated}/{len(yf_map)} precios actualizados")
    except Exception as e:
        print(f"  ⚠️ Error yfinance: {e}")

    df["fecha_actualizacion"] = str(date.today())
    return df


def write_cartera(df: pd.DataFrame):
    sb = get_client()
    sb.table("cartera_actual").delete().neq("id", 0).execute()
    records = df.drop(columns=["id", "created_at"], errors="ignore").to_dict("records")
    for r in records:
        for k, v in list(r.items()):
            if pd.isna(v):
                r[k] = None
    sb.table("cartera_actual").insert(records).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-prices", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 UPDATE CARTERA_ACTUAL (idempotente desde base)")
    print("=" * 60)

    # 1. Base inmutable
    print(f"\n📌 Snapshot base: {SNAPSHOT_DATE} (desde cartera_base.py)")
    base = get_base()
    df_cart = pd.DataFrame(base)
    print(f"   {len(df_cart)} posiciones base")

    # 2. Cargar movimientos posteriores
    print("\n📊 Cargando transacciones Racional > snapshot...")
    df_rac = pd.DataFrame(fetch_all("racional_transacciones", "fecha", SNAPSHOT_DATE))
    print(f"   {len(df_rac)} transacciones")

    print("\n📊 Cargando compras Buda > snapshot...")
    df_buda = pd.DataFrame(fetch_all("buda_crypto", "fecha", SNAPSHOT_DATE))
    print(f"   {len(df_buda)} compras")

    # 3. Aplicar diffs
    print("\n▶ Aplicando Racional internacional...")
    df_cart, log_r = apply_racional(df_cart, df_rac)
    for l in log_r: print(l)

    print("\n▶ Aplicando Buda crypto...")
    df_cart, log_b = apply_buda(df_cart, df_buda)
    for l in log_b: print(l)

    # 4. Precios
    if not args.no_prices:
        print("\n▶ Refrescando precios (yfinance)...")
        df_cart = update_prices(df_cart)

    # 5. Resumen
    df_cart["valor_usd"] = pd.to_numeric(df_cart["cantidad"], errors="coerce") * pd.to_numeric(df_cart["precio_actual"], errors="coerce")
    USD_CLP = 901.76
    df_cart["valor_clp"] = df_cart.apply(
        lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP,
        axis=1
    )
    total = df_cart["valor_clp"].sum()
    print(f"\n📊 RESULTADO:")
    print(f"   {len(df_cart)} posiciones")
    print(f"   Total: ${total:,.0f} CLP")
    grp = df_cart.groupby("mercado")["valor_clp"].sum().sort_values(ascending=False)
    for m, v in grp.items():
        print(f"     {m:20s}: ${v:>15,.0f}")

    # Drop columnas auxiliares antes de escribir
    df_cart = df_cart.drop(columns=["valor_usd", "valor_clp"], errors="ignore")

    if args.dry_run:
        print("\n⚠️ DRY RUN — no se escribió a Supabase")
    else:
        print(f"\n▶ Escribiendo {len(df_cart)} posiciones a Supabase...")
        write_cartera(df_cart)
        print("✅ cartera_actual actualizada")

    print("=" * 60)


if __name__ == "__main__":
    main()
