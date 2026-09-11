#!/bin/bash
# ============================================================
# Script de inicio del Financial Dashboard
# Se ejecuta automáticamente via LaunchAgent al hacer login
# ============================================================

export HOME="/Users/matiasmollerv"
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd /Users/matiasmollerv/Projects/financial-dashboard

# Activar entorno virtual
source /Users/matiasmollerv/Projects/financial-dashboard/venv/bin/activate

# Iniciar Streamlit
exec /Users/matiasmollerv/Projects/financial-dashboard/venv/bin/python \
    -m streamlit run \
    /Users/matiasmollerv/Projects/financial-dashboard/dashboard/app.py \
    --server.port=8501 \
    --server.headless=true \
    --browser.gatherUsageStats=false
