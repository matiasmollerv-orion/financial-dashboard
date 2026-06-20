# ============================================================
# TWR CALCULATOR — Time-Weighted Return como lo calcula Racional
#
# Metodología (Racional Help Center, ago 2024):
#   TWR = ∏(1 + r_i) - 1
#   donde r_i = (V_fin - F_i) / V_ini - 1
#   y los sub-períodos se cortan en cada flujo (compra/venta).
#
# En implementación simplificada: cortes diarios.
#   r_día = (V_día - F_día) / V_día_anterior - 1
#
# Resultado representa: "cómo le ha ido a la cartera en el tiempo,
# sin considerar el timing de depósitos/retiros."
#
# Limitación: este script calcula TWR desde SNAPSHOT_DATE hasta hoy.
# Para "TWR desde el inicio" (que incluye años previos), hay que
# componer con el TWR_PRE_SNAPSHOT que el usuario reporta de Racional
# al snapshot date.
#
# Uso:
#   python -m intelligence.twr_calculator
#   python -m intelligence.twr_calculator --start 2026-04-30
# ============================================================

import sys, argparse, warnings
from datetime import datetime, date, timedelta
warnings.filterwarnings("ignore")

sys.path.insert(0, ".")
import pandas as pd
import numpy as np
from database.supabase_client import get_client
from cartera_base import ACCIONES_CL, STOCKS_INTL, CRYPTO, SNAPSHOT_DATE

USD_CLP = 901.76  # TODO: histórico, por ahora fijo


# ── HELPERS ──────────────────────────────────────────────────
def get_ticker_meta(plataforma: str = None) -> dict:
    """Map ticker → {mercado, moneda, cantidad_base}.

    plataforma: filtro opcional:
      None/"Todo"   → todos los tickers
      "Racional Internacional" → mercado=internacional (sin _STG)
      "Racional Nacional"      → mercado=nacional sin sufijo _STG
      "Santander Corredora"    → tickers con sufijo _STG
      "Crypto (Buda)"          → mercado=crypto
    """
    meta = {}
    for row in ACCIONES_CL + STOCKS_INTL + CRYPTO:
        tk = row["ticker"]
        mercado = row["mercado"]

        # Filtrar por plataforma si se pide
        if plataforma and plataforma not in (None, "Todo"):
            if plataforma == "Racional Internacional" and mercado != "internacional":
                continue
            elif plataforma == "Racional Nacional" and (mercado != "nacional" or tk.endswith("_STG")):
                continue
            elif plataforma == "Santander Corredora" and not tk.endswith("_STG"):
                continue
            elif plataforma == "Crypto (Buda)" and mercado != "crypto":
                continue

        meta[tk] = {
            "mercado": mercado,
            "moneda":  row["moneda"],
            "cantidad_base": row["cantidad"],
        }
    return meta


def yf_ticker_for(ticker: str, mercado: str) -> str:
    if mercado == "nacional":
        return f"{ticker}.SN"
    if mercado == "crypto":
        return f"{ticker}-USD"
    return ticker


def fetch_all_pagination(table: str, filter_col: str = None,
                         filter_op: str = "gt", filter_val=None,
                         page_size: int = 1000) -> list[dict]:
    sb = get_client()
    rows, page = [], 0
    while True:
        q = sb.table(table).select("*").range(page*page_size, page*page_size + page_size - 1)
        if filter_col:
            if filter_op == "gt":
                q = q.gt(filter_col, filter_val)
            elif filter_op == "gte":
                q = q.gte(filter_col, filter_val)
        r = q.execute()
        rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return rows


# ── DATOS HISTÓRICOS DE PRECIOS ──────────────────────────────
def fetch_prices(yf_tickers: list, start: str, end: str) -> pd.DataFrame:
    """DataFrame de precios Close diarios. Index: fecha. Columnas: yf_tickers."""
    import yfinance as yf
    raw = yf.download(yf_tickers, start=start, end=end, interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    if raw.empty:
        return pd.DataFrame()

    if len(yf_tickers) == 1:
        close = raw[["Close"]].copy()
        close.columns = [yf_tickers[0]]
    else:
        # Multi-ticker → es MultiIndex (ticker, campo)
        try:
            close = raw.xs("Close", axis=1, level=1)
        except KeyError:
            close = raw.xs("Close", axis=1, level=0)
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close


# ── CÁLCULO PRINCIPAL ─────────────────────────────────────────
def compute_twr(start_date: str = SNAPSHOT_DATE,
                end_date: str = None,
                verbose: bool = True,
                plataforma: str = None) -> dict:
    """
    Calcula TWR para cualquier período. Dos modos:
      - Si start_date >= SNAPSHOT_DATE: usa cantidad_base del snapshot + deltas (modo original)
      - Si start_date < SNAPSHOT_DATE: reconstruye posiciones desde cero usando TODO el
        historial de transacciones (modo histórico completo)
    """
    if end_date is None:
        end_date = date.today().isoformat()

    # ¿Período pre-snapshot?
    pre_snapshot = pd.Timestamp(start_date) < pd.Timestamp(SNAPSHOT_DATE)

    if verbose:
        mode = "HISTÓRICO (desde transacciones)" if pre_snapshot else "POST-SNAPSHOT (desde base)"
        print(f"\n📅 Calculando TWR: {start_date} → {end_date} [{mode}]")

    # 1. Ticker meta (filtrado por plataforma si se pide)
    meta = get_ticker_meta(plataforma)

    # 2. Transacciones — traer TODAS si modo histórico, o solo post-start si post-snapshot
    if pre_snapshot:
        # Modo histórico: traer TODAS las transacciones para reconstruir posiciones
        rac = pd.DataFrame(fetch_all_pagination("racional_transacciones"))
        buda = pd.DataFrame(fetch_all_pagination("buda_crypto"))
    else:
        rac = pd.DataFrame(fetch_all_pagination("racional_transacciones", "fecha", "gt", start_date))
        buda = pd.DataFrame(fetch_all_pagination("buda_crypto", "fecha", "gt", start_date))

    if not rac.empty:
        rac["fecha"] = pd.to_datetime(rac["fecha"]).dt.tz_localize(None)
        for c in ["acciones", "monto_usd", "monto_clp"]:
            rac[c] = pd.to_numeric(rac[c], errors="coerce").fillna(0)
    if not buda.empty:
        buda["fecha"] = pd.to_datetime(buda["fecha"]).dt.tz_localize(None)
        buda["cantidad"] = pd.to_numeric(buda["cantidad"], errors="coerce").fillna(0)

    # Filtrar transacciones por plataforma
    if plataforma and plataforma not in (None, "Todo"):
        if plataforma == "Racional Internacional":
            if not rac.empty:
                rac = rac[rac["mercado"] == "internacional"]
            buda = pd.DataFrame()  # no incluir crypto
        elif plataforma == "Racional Nacional":
            if not rac.empty:
                rac = rac[rac["mercado"] == "nacional"]
            buda = pd.DataFrame()
        elif plataforma == "Santander Corredora":
            rac = pd.DataFrame()   # Santander no tiene transacciones en Racional
            buda = pd.DataFrame()
        elif plataforma == "Crypto (Buda)":
            rac = pd.DataFrame()   # solo buda
            # buda se mantiene

    if verbose:
        plat_str = f" [{plataforma}]" if plataforma else ""
        print(f"   {len(rac)} transacciones Racional · {len(buda)} compras Buda{plat_str}")

    # 3. Descubrir todos los tickers que aparecen en transacciones
    if not rac.empty:
        for _, row in rac.iterrows():
            tk = row["ticker"]
            if tk and tk not in meta and tk != "PORTFOLIO_CL":
                meta[tk] = {
                    "mercado": row.get("mercado", "internacional"),
                    "moneda": "USD" if row.get("mercado") != "nacional" else "CLP",
                    "cantidad_base": 0,
                }

    all_tickers = sorted(meta.keys())

    # 4. Range de fechas
    dates = pd.date_range(start_date, end_date, freq="D")

    # 5. Construir DataFrame de cantidades diarias por ticker
    if pre_snapshot:
        # Modo histórico: reconstruir posiciones desde TODAS las transacciones.
        # Transacciones ANTES del start_date → posición inicial (se aplican a todo el rango).
        # Transacciones DENTRO del período → se aplican desde su fecha en adelante.
        start_ts = pd.Timestamp(start_date)
        qty_df = pd.DataFrame(0.0, index=dates, columns=all_tickers)

        if not rac.empty:
            for _, row in rac.iterrows():
                tk = row["ticker"]
                if tk == "PORTFOLIO_CL" or tk not in qty_df.columns:
                    continue
                if row["mercado"] == "nacional":
                    continue
                delta = float(row["acciones"]) if row["tipo"] == "compra" else -float(row["acciones"])
                tx_date = row["fecha"].normalize()
                if tx_date < start_ts:
                    # Transacción anterior al período → afecta TODA la serie (posición inicial)
                    qty_df[tk] = qty_df[tk].astype(np.float64) + delta
                else:
                    # Transacción dentro del período → afecta desde su fecha
                    mask = qty_df.index >= tx_date
                    qty_df.loc[mask, tk] = qty_df.loc[mask, tk].astype(np.float64) + delta

        if not buda.empty:
            for _, row in buda.iterrows():
                tk = row["activo"]
                if tk not in qty_df.columns:
                    qty_df[tk] = 0.0
                    meta[tk] = {"mercado": "crypto", "moneda": "USD", "cantidad_base": 0}
                    all_tickers = sorted(set(all_tickers + [tk]))
                tx_date = row["fecha"].normalize()
                if tx_date < start_ts:
                    qty_df[tk] = qty_df[tk].astype(np.float64) + float(row["cantidad"])
                else:
                    mask = qty_df.index >= tx_date
                    qty_df.loc[mask, tk] = qty_df.loc[mask, tk].astype(np.float64) + float(row["cantidad"])

        # Eliminar tickers que nunca tuvieron posición en el período
        active_tickers = [tk for tk in qty_df.columns if qty_df[tk].abs().max() > 0]
        qty_df = qty_df[active_tickers]
        all_tickers = active_tickers

    else:
        # Modo post-snapshot: usar cantidad_base como antes
        qty_df = pd.DataFrame(
            {tk: np.full(len(dates), float(meta[tk]["cantidad_base"]), dtype=np.float64)
             for tk in all_tickers},
            index=dates,
        )
        qty_df = qty_df.astype(np.float64)

        if not rac.empty:
            for _, row in rac.iterrows():
                tk = row["ticker"]
                if tk == "PORTFOLIO_CL" or tk not in qty_df.columns:
                    continue
                if row["mercado"] == "nacional":
                    continue
                delta = float(row["acciones"]) if row["tipo"] == "compra" else -float(row["acciones"])
                mask = qty_df.index >= row["fecha"].normalize()
                qty_df.loc[mask, tk] = qty_df.loc[mask, tk].astype(np.float64) + delta

        if not buda.empty:
            for _, row in buda.iterrows():
                tk = row["activo"]
                if tk not in qty_df.columns:
                    continue
                mask = qty_df.index >= row["fecha"].normalize()
                qty_df.loc[mask, tk] = qty_df.loc[mask, tk].astype(np.float64) + float(row["cantidad"])

    # 6. Descargar precios históricos
    yf_map = {tk: yf_ticker_for(tk, meta[tk]["mercado"]) for tk in all_tickers}
    yf_unique = list(set(yf_map.values()))

    start_buf = (pd.Timestamp(start_date) - timedelta(days=5)).strftime("%Y-%m-%d")
    end_buf = (pd.Timestamp(end_date) + timedelta(days=2)).strftime("%Y-%m-%d")

    if verbose:
        print(f"   📡 Descargando precios de {len(yf_unique)} tickers…")

    prices_raw = fetch_prices(yf_unique, start_buf, end_buf)

    if prices_raw.empty:
        print("❌ No se pudieron bajar precios")
        return None

    prices = pd.DataFrame(index=prices_raw.index)
    for tk in all_tickers:
        yf_tk = yf_map[tk]
        if yf_tk in prices_raw.columns:
            prices[tk] = prices_raw[yf_tk]
        else:
            prices[tk] = np.nan

    # Re-indexar al calendario diario + forward fill (días sin precio = previo)
    prices = prices.reindex(dates).ffill().bfill()

    # 7. Calcular valor diario en CLP
    valor_df = pd.DataFrame(0.0, index=dates, columns=all_tickers)
    for tk in all_tickers:
        if tk not in prices.columns:
            continue
        v_local = qty_df[tk] * prices[tk]
        if meta[tk]["moneda"] == "USD":
            valor_df[tk] = v_local * USD_CLP
        else:
            valor_df[tk] = v_local

    portfolio_value = valor_df.sum(axis=1)

    # 8. Calcular flujos netos diarios en CLP
    flujo = pd.Series(0.0, index=dates)
    if not rac.empty:
        for _, row in rac.iterrows():
            fecha = row["fecha"].normalize()
            if fecha not in flujo.index:
                continue
            if row["mercado"] == "internacional":
                monto = row["monto_usd"] * USD_CLP
            else:
                monto = row["monto_clp"]
            if row["tipo"] == "compra":
                flujo.loc[fecha] += monto
            else:
                flujo.loc[fecha] -= monto

    if not buda.empty:
        for _, row in buda.iterrows():
            fecha = row["fecha"].normalize()
            if fecha not in flujo.index:
                continue
            tk = row["activo"]
            if tk in prices.columns:
                precio = prices.loc[fecha, tk]
                if pd.notna(precio):
                    monto_clp = row["cantidad"] * precio * USD_CLP
                    flujo.loc[fecha] += monto_clp

    # 9. Calcular retornos diarios TWR
    daily_return = pd.Series(0.0, index=dates)
    for i in range(1, len(dates)):
        V_prev = portfolio_value.iloc[i-1]
        V_curr = portfolio_value.iloc[i]
        F = flujo.iloc[i]
        if V_prev > 0:
            daily_return.iloc[i] = (V_curr - F) / V_prev - 1

    twr_acum = (1 + daily_return).prod() - 1

    # Retorno monetario (simple, no TWR)
    valor_ini = portfolio_value.iloc[0]
    valor_fin = portfolio_value.iloc[-1]
    flujo_total = flujo.sum()
    ganancia_pesos = valor_fin - valor_ini - flujo_total

    return {
        "twr_pct":           twr_acum * 100,
        "twr_acum":          twr_acum,
        "dias":              len(dates),
        "valor_inicial":     valor_ini,
        "valor_final":       valor_fin,
        "flujos_netos":      flujo_total,
        "ganancia_pesos":    ganancia_pesos,
        "daily_return":      daily_return,
        "portfolio_value":   portfolio_value,
        "flujo":             flujo,
    }


# ── COMPOSICIÓN CON TWR PRE-SNAPSHOT ─────────────────────────
def compose_twr(twr_pre: float, twr_post: float) -> float:
    """
    Compone dos TWR: (1 + pre) × (1 + post) - 1
    twr_pre y twr_post como decimal (ej 0.46 = 46%).
    """
    return (1 + twr_pre) * (1 + twr_post) - 1


# ── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=SNAPSHOT_DATE,
                        help=f"Fecha de inicio (default {SNAPSHOT_DATE})")
    parser.add_argument("--end", default=None, help="Fecha fin (default hoy)")
    parser.add_argument("--twr-pre", type=float, default=None,
                        help="TWR previo a la fecha de inicio (decimal, ej 0.46 para 46%). Si se entrega, compone.")
    args = parser.parse_args()

    print("=" * 60)
    print("📈 TWR CALCULATOR (Time-Weighted Return — método Racional)")
    print("=" * 60)

    result = compute_twr(args.start, args.end)
    if not result:
        return

    print(f"\n📊 RESULTADO:")
    print(f"   Período:        {args.start} → {args.end or date.today().isoformat()} ({result['dias']} días)")
    print(f"   Valor inicial:  ${result['valor_inicial']:,.0f} CLP")
    print(f"   Valor final:    ${result['valor_final']:,.0f} CLP")
    print(f"   Flujos netos:   ${result['flujos_netos']:,.0f} CLP")
    print(f"   Ganancia $$:    ${result['ganancia_pesos']:,.0f} CLP")
    print(f"")
    print(f"   ▶ TWR del período:  {result['twr_pct']:.2f}%")

    if args.twr_pre is not None:
        twr_total = compose_twr(args.twr_pre, result["twr_acum"])
        print(f"")
        print(f"   TWR pre-snapshot:   {args.twr_pre*100:.2f}%")
        print(f"   TWR del período:    {result['twr_pct']:.2f}%")
        print(f"   ▶ TWR DESDE INICIO: {twr_total*100:.2f}%")

    print("=" * 60)


if __name__ == "__main__":
    main()
