#!/bin/bash
# ============================================================
# ACTUALIZACIÓN SEMANAL — Financial Dashboard
# Descarga nuevos PDFs de Gmail y actualiza Supabase
# ============================================================

SCRIPT_DIR="$HOME/Documents/Claude/FinancialDashboard"
LOG_FILE="$SCRIPT_DIR/logs/weekly_update.log"
VENV="$SCRIPT_DIR/venv/bin/python"

mkdir -p "$SCRIPT_DIR/logs"

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') — Iniciando actualización semanal" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$SCRIPT_DIR" || exit 1

# 1. Santander (tarjeta + cuenta corriente)
echo "--- Santander ---" >> "$LOG_FILE"
"$VENV" load_santander.py >> "$LOG_FILE" 2>&1

# 2. Racional compras (si existe el script)
if [ -f "load_racional.py" ]; then
    echo "--- Racional compras ---" >> "$LOG_FILE"
    "$VENV" load_racional.py >> "$LOG_FILE" 2>&1
fi

# 3. Racional ventas
if [ -f "load_racional_ventas.py" ]; then
    echo "--- Racional ventas ---" >> "$LOG_FILE"
    "$VENV" load_racional_ventas.py >> "$LOG_FILE" 2>&1
fi

# 4. Buda (si existe el script)
if [ -f "load_buda.py" ]; then
    echo "--- Buda ---" >> "$LOG_FILE"
    "$VENV" load_buda.py >> "$LOG_FILE" 2>&1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') — Actualización completada" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
