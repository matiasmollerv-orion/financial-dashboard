# ============================================================
# SUPABASE CLIENT
# Carga y consulta datos en la base de datos
# ============================================================

import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def _get_secret(key: str) -> str:
    """Lee desde st.secrets (Streamlit Cloud) con fallback a .env (local)."""
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key)

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en el .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── CARGA DE DATOS ────────────────────────────────────────

def _clean_rows(registros: list[dict], exclude_keys: list = []) -> list[dict]:
    """Limpia registros para inserción: convierte fechas, elimina NaN y claves excluidas."""
    import math
    clean = []
    for r in registros:
        row = {k: v for k, v in r.items() if k not in exclude_keys}
        if hasattr(row.get("fecha"), "isoformat"):
            row["fecha"] = row["fecha"].isoformat()
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
        clean.append(row)
    return clean


def _insert_batch(table: str, registros: list[dict], batch_size: int = 100) -> int:
    """Inserta en lotes ignorando duplicados."""
    if not registros:
        return 0
    sb = get_client()
    total = 0
    for i in range(0, len(registros), batch_size):
        batch = registros[i:i+batch_size]
        try:
            result = sb.table(table).insert(batch, returning="minimal").execute()
            total += len(batch)
        except Exception as e:
            # Si hay duplicados, insertar uno a uno ignorando los que fallen
            for row in batch:
                try:
                    sb.table(table).insert(row, returning="minimal").execute()
                    total += 1
                except Exception:
                    pass
    return total


def upsert_racional(registros: list[dict]) -> int:
    clean = _clean_rows(registros, exclude_keys=["detalle"])
    return _insert_batch("racional_transacciones", clean)


def upsert_racional_nacional_detalle(registros: list[dict], transaccion_id: int) -> int:
    if not registros:
        return 0
    clean = _clean_rows(registros)
    for r in clean:
        r["transaccion_id"] = transaccion_id
    return _insert_batch("racional_nacional_detalle", clean)


def upsert_buda(registros: list[dict]) -> int:
    clean = _clean_rows(registros)
    return _insert_batch("buda_crypto", clean)


def upsert_vector_capital(registros: list[dict]) -> int:
    clean = _clean_rows(registros)
    return _insert_batch("vector_capital_comprobantes", clean)


def upsert_gastos(registros: list[dict]) -> int:
    clean = _clean_rows(registros)
    return _insert_batch("santander_gastos", clean)


def upsert_cuenta(registros: list[dict]) -> int:
    clean = _clean_rows(registros)
    return _insert_batch("santander_cuenta", clean)


def insertar_ingreso(fecha: str, concepto: str, monto: float, moneda: str = "CLP") -> int:
    sb = get_client()
    result = sb.table("ingresos").insert({
        "fecha": fecha,
        "concepto": concepto,
        "monto": monto,
        "moneda": moneda,
        "fuente": "manual"
    }).execute()
    return len(result.data)


# ── LECTURA DE DATOS ──────────────────────────────────────

def _fetch_all(query, page_size: int = 1000) -> list:
    """Pagina automáticamente para superar el límite de 1000 filas de Supabase."""
    all_data = []
    page = 0
    while True:
        start = page * page_size
        result = query.range(start, start + page_size - 1).execute()
        all_data.extend(result.data)
        if len(result.data) < page_size:
            break
        page += 1
    return all_data


def get_racional_transacciones(mercado: str = None) -> pd.DataFrame:
    sb = get_client()
    q = sb.table("racional_transacciones").select("*").order("fecha", desc=True)
    if mercado:
        q = q.eq("mercado", mercado)
    return pd.DataFrame(_fetch_all(q))


def get_buda_crypto(activo: str = None) -> pd.DataFrame:
    sb = get_client()
    q = sb.table("buda_crypto").select("*").order("fecha", desc=True)
    if activo:
        q = q.eq("activo", activo)
    return pd.DataFrame(_fetch_all(q))


def get_gastos(desde: str = None, hasta: str = None) -> pd.DataFrame:
    sb = get_client()
    q = sb.table("santander_gastos").select("*").order("fecha", desc=True)
    if desde:
        q = q.gte("fecha", desde)
    if hasta:
        q = q.lte("fecha", hasta)
    return pd.DataFrame(_fetch_all(q))


def get_ingresos() -> pd.DataFrame:
    sb = get_client()
    result = sb.table("ingresos").select("*").order("fecha", desc=True).execute()
    return pd.DataFrame(result.data)


def get_comisiones() -> pd.DataFrame:
    sb = get_client()
    result = sb.table("vector_capital_comprobantes").select("*").eq("es_comision", True).order("fecha", desc=True).execute()
    return pd.DataFrame(result.data)
