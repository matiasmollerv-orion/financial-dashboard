# 📊 Financial Dashboard Personal

Dashboard personal para seguimiento de gastos, inversiones y proyecciones patrimoniales.

## Fuentes de datos

| Fuente | Tipo | Categoría |
|--------|------|-----------|
| Santander - Tarjeta Crédito | PDF mensual (CLP + USD) | Gastos |
| Santander - Cuenta Corriente | PDF mensual | Movimientos |
| Racional - Transacciones | Email (cuerpo) | Inversiones |
| Racional - Comisiones | PDF mensual | Comisiones |
| Racional - Acciones Nacionales | Email (cuerpo) | Inversiones |
| Buda - Compra programada | Email (cuerpo) | Crypto (BTC/ETH) |

## Estructura del proyecto

```
FinancialDashboard/
├── config/               # Configuración de fuentes de correo
├── data/
│   ├── raw/              # PDFs descargados (no van a GitHub)
│   ├── processed/        # Datos parseados
│   └── backups/          # Respaldos por fecha
├── extractors/           # Módulos de extracción por fuente
├── database/             # Cliente Supabase
├── dashboard/            # App Streamlit
└── notebooks/            # Exploración y testing
```

## Setup inicial

1. Copiar `.env.example` → `.env` y completar credenciales
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar Gmail API (ver instrucciones en `extractors/gmail_client.py`)
4. Ejecutar dashboard: `streamlit run dashboard/app.py`

## Stack

- **Backend:** Python + pandas
- **Base de datos:** Supabase (PostgreSQL)
- **Dashboard:** Streamlit
- **Hosting:** Streamlit Community Cloud (gratuito)
