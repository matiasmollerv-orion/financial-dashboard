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


def _safe_qty(value) -> float:
    """Convierte un valor a float, retornando 0.0 si es NaN/None/inválido.
    CRÍTICO: si una transacción tiene acciones=NaN (parsing fallido),
    NUNCA debemos aplicarla porque contamina la cartera entera con NaN."""
    if value is None:
        return 0.0
    try:
        v = float(value)
        if pd.isna(v) or not pd.notna(v):
            return 0.0
        return v
    except (ValueError, TypeError):
        return 0.0


def _safe_existing(value) -> float:
    """Lee valor existente de la cartera, tratando NaN como 0."""
    if value is None:
        return 0.0
    try:
        v = float(value)
        return 0.0 if pd.isna(v) else v
    except (ValueError, TypeError):
        return 0.0


def apply_racional(df_cart: pd.DataFrame, df_rac: pd.DataFrame) -> tuple:
    """Aplica compras/ventas Racional internacional sobre cartera.
    DEFENSIVO contra NaN: si una transacción tiene acciones=NaN (parsing fallido),
    se ignora SILENCIOSAMENTE en vez de contaminar la cantidad con NaN."""
    log = []
    if df_rac.empty:
        return df_cart, log

    df_c = df_cart.copy().set_index("ticker")
    # Asegurar dtype float en cantidad
    df_c["cantidad"] = pd.to_numeric(df_c["cantidad"], errors="coerce").fillna(0).astype(float)

    intl = df_rac[df_rac["mercado"] == "internacional"].copy()
    intl["acciones"] = pd.to_numeric(intl["acciones"], errors="coerce")
    intl["precio_usd"] = pd.to_numeric(intl["precio_usd"], errors="coerce")

    skipped_nan = 0
    for _, row in intl[intl["tipo"] == "compra"].iterrows():
        tk = row["ticker"]
        qty = _safe_qty(row.get("acciones"))
        if qty <= 0:
            if pd.isna(row.get("acciones")):
                skipped_nan += 1
            continue
        if tk in df_c.index:
            existing = _safe_existing(df_c.at[tk, "cantidad"])
            df_c.at[tk, "cantidad"] = existing + qty
        else:
            df_c.loc[tk] = pd.Series({
                "empresa": row.get("empresa", tk),
                "mercado": "internacional",
                "cantidad": qty,
                "precio_compra": _safe_qty(row.get("precio_usd")),
                "precio_actual": _safe_qty(row.get("precio_usd")),
                "moneda": "USD",
                "fecha_actualizacion": str(date.today()),
            })
            log.append(f"  🆕 {tk}: ticker nuevo")

    for _, row in intl[intl["tipo"] == "venta"].iterrows():
        tk = row["ticker"]
        qty = _safe_qty(row.get("acciones"))
        if qty <= 0:
            if pd.isna(row.get("acciones")):
                skipped_nan += 1
            continue
        if tk in df_c.index:
            existing = _safe_existing(df_c.at[tk, "cantidad"])
            df_c.at[tk, "cantidad"] = max(existing - qty, 0)

    if skipped_nan > 0:
        log.append(f"  ⚠️ {skipped_nan} transacciones ignoradas por parsing fallido (acciones=NaN)")

    # Filtro seguro: fillna(0) protege contra cualquier NaN residual
    df_c = df_c[df_c["cantidad"].fillna(0) > 0]
    log.append(f"  ✅ Aplicadas {len(intl)} transacciones internacionales ({len(df_c)} posiciones resultantes)")
    return df_c.reset_index(), log


def apply_buda(df_cart: pd.DataFrame, df_buda: pd.DataFrame) -> tuple:
    """Suma compras crypto Buda (defensivo contra NaN)."""
    log = []
    if df_buda.empty:
        return df_cart, log

    df_c = df_cart.copy().set_index("ticker")
    df_c["cantidad"] = pd.to_numeric(df_c["cantidad"], errors="coerce").fillna(0).astype(float)

    df_buda["cantidad"] = pd.to_numeric(df_buda["cantidad"], errors="coerce")
    grp = df_buda.groupby("activo")["cantidad"].sum()

    for activo, qty in grp.items():
        safe_qty = _safe_qty(qty)
        if safe_qty <= 0:
            continue
        if activo in df_c.index:
            existing = _safe_existing(df_c.at[activo, "cantidad"])
            df_c.at[activo, "cantidad"] = existing + safe_qty
        else:
            df_c.loc[activo] = pd.Series({
                "empresa": activo,
                "mercado": "crypto",
                "cantidad": safe_qty,
                "precio_compra": 0.0,
                "precio_actual": 0.0,
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
            # Santander stocks use _STG suffix; strip it for yfinance
            base_tk = tk.replace("_STG", "") if tk.endswith("_STG") else tk
            # ENELCHILE is the BCS ticker, maps to ENELCHILE.SN in yfinance
            yf_map[tk] = f"{base_tk}.SN"
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


def get_previous_cartera_total() -> float:
    """Lee el total previo de cartera_actual (antes de sobreescribir).
    Sirve para sanity check: si el nuevo es <75% del previo, abortamos."""
    USD_CLP_LOCAL = 901.76
    try:
        sb = get_client()
        r = sb.table("cartera_actual").select("*").execute()
        if not r.data:
            return 0.0
        df = pd.DataFrame(r.data)
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
        df["precio_actual"] = pd.to_numeric(df["precio_actual"], errors="coerce").fillna(0)
        df["valor_usd"] = df["cantidad"] * df["precio_actual"]
        df["valor_clp"] = df.apply(
            lambda r: r["valor_usd"] if r.get("moneda") == "CLP" else r["valor_usd"] * USD_CLP_LOCAL,
            axis=1
        )
        return float(df["valor_clp"].sum())
    except Exception:
        return 0.0


# ── VALIDACIONES ESTRUCTURALES ──────────────────────────────
# Si alguna falla, update_cartera.py ABORTA y no sobreescribe.
# Esto previene que código roto destruya la cartera.

# Tickers que SIEMPRE deben existir (posiciones grandes que nunca deberían desaparecer)
REQUIRED_TICKERS = {
    "nacional": ["BCI", "CENCOSUD", "FALABELLA", "ITAUCL", "LTM",
                  "ENELCHILE_STG", "LTM_STG"],
    "internacional": ["NVDA", "GOOGL", "VOO", "MSFT", "NU", "TSM", "MELI"],
    "crypto": ["BTC", "ETH"],
}
MIN_POSITIONS = 90          # base actual tiene 97; si baja de 90, algo está roto
MIN_NACIONAL_CLP = 15_000_000   # nacional nunca debería estar bajo 15M CLP
MIN_INTL_USD = 50_000           # internacional nunca debería estar bajo 50K USD


def validate_cartera(df: pd.DataFrame) -> list[str]:
    """Validaciones estructurales. Retorna lista de errores (vacía = OK)."""
    errors = []

    # 1. Mínimo de posiciones
    n = len(df)
    if n < MIN_POSITIONS:
        errors.append(f"Solo {n} posiciones (mínimo {MIN_POSITIONS}). Probablemente cartera_base.py incompleta.")

    # 2. Tickers obligatorios
    tickers_presentes = set(df["ticker"].str.upper())
    for mercado, required in REQUIRED_TICKERS.items():
        for tk in required:
            if tk.upper() not in tickers_presentes:
                errors.append(f"Ticker obligatorio FALTA: {tk} ({mercado})")

    # 3. Valor mínimo por mercado
    df_v = df.copy()
    df_v["cantidad"] = pd.to_numeric(df_v["cantidad"], errors="coerce").fillna(0)
    df_v["precio_actual"] = pd.to_numeric(df_v["precio_actual"], errors="coerce").fillna(0)
    df_v["_val"] = df_v["cantidad"] * df_v["precio_actual"]

    nac_total = df_v[df_v["mercado"] == "nacional"]["_val"].sum()
    if nac_total < MIN_NACIONAL_CLP:
        errors.append(f"Nacional ${nac_total:,.0f} CLP < mínimo ${MIN_NACIONAL_CLP:,.0f}. Faltan stocks.")

    intl_total = df_v[df_v["mercado"] == "internacional"]["_val"].sum()
    if intl_total < MIN_INTL_USD:
        errors.append(f"Internacional USD {intl_total:,.0f} < mínimo USD {MIN_INTL_USD:,.0f}. Faltan stocks.")

    # 4. Cantidades no deben ser NaN o negativas
    nan_rows = df_v[df_v["cantidad"].isna() | (df_v["cantidad"] < 0)]
    if not nan_rows.empty:
        bad_tks = nan_rows["ticker"].tolist()
        errors.append(f"Cantidades NaN/negativas en: {bad_tks}")

    return errors


def write_cartera(df: pd.DataFrame, force: bool = False):
    """Escribe cartera_actual con múltiples sanity checks.
    NUNCA sobreescribe si las validaciones estructurales fallan (ni con --force).
    El --force solo bypasea el check de caída porcentual vs anterior."""
    USD_CLP_LOCAL = 901.76
    sb = get_client()

    # ── Validación estructural (NUNCA se puede saltar) ────
    structural_errors = validate_cartera(df)
    if structural_errors:
        print(f"\n🚨 VALIDACIÓN ESTRUCTURAL FALLÓ ({len(structural_errors)} errores):")
        for e in structural_errors:
            print(f"   ❌ {e}")
        print(f"\n   La cartera anterior se MANTIENE intacta.")
        print(f"   Esto NO se puede saltar con --force. Revisa cartera_base.py.")
        raise RuntimeError(
            f"Validación estructural falló: {'; '.join(structural_errors)}"
        )

    # ── Sanity check vs cartera anterior (se puede saltar con --force) ────
    df_local = df.copy()
    df_local["cantidad"] = pd.to_numeric(df_local["cantidad"], errors="coerce").fillna(0)
    df_local["precio_actual"] = pd.to_numeric(df_local["precio_actual"], errors="coerce").fillna(0)
    df_local["_valor_usd"] = df_local["cantidad"] * df_local["precio_actual"]
    df_local["_valor_clp"] = df_local.apply(
        lambda r: r["_valor_usd"] if r.get("moneda") == "CLP" else r["_valor_usd"] * USD_CLP_LOCAL,
        axis=1
    )
    new_total = float(df_local["_valor_clp"].sum())
    prev_total = get_previous_cartera_total()

    if prev_total > 0 and not force:
        ratio = new_total / prev_total
        if ratio < 0.75:
            drop_pct = (1 - ratio) * 100
            print(f"\n🚨 SANITY CHECK FALLÓ:")
            print(f"   Cartera previa: ${prev_total:,.0f} CLP")
            print(f"   Cartera nueva:  ${new_total:,.0f} CLP")
            print(f"   Caída: -{drop_pct:.1f}%")
            print(f"\n   No voy a sobreescribir. La cartera anterior se mantiene.")
            print(f"   Para forzar de todos modos: usa --force")
            raise RuntimeError(
                f"Cartera cae {drop_pct:.1f}% vs anterior. "
                f"Probablemente bug en update. Aborto para no perder data."
            )
        elif ratio < 0.90:
            print(f"\n⚠️ ADVERTENCIA: Cartera cae {(1-ratio)*100:.1f}% vs anterior.")
            print(f"   Previa: ${prev_total:,.0f} → Nueva: ${new_total:,.0f}")
            print(f"   Continúo escribiendo, pero revisa si es esperado.")

    # ── OK, escribir ──────────────────────────────────────
    sb.table("cartera_actual").delete().neq("id", 0).execute()
    records = df.drop(columns=["id", "created_at", "_valor_usd", "_valor_clp"], errors="ignore").to_dict("records")
    for r in records:
        for k, v in list(r.items()):
            if pd.isna(v):
                r[k] = None
    sb.table("cartera_actual").insert(records).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-prices", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Bypass sanity check (cartera cae >25% se permite)")
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
        try:
            write_cartera(df_cart, force=args.force)
            print("✅ cartera_actual actualizada")
        except RuntimeError as e:
            print(f"\n❌ ABORTADO: {e}")
            sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
