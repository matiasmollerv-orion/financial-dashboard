# 📱 Setup: Notificaciones iPhone → Dashboard en tiempo real

**Costo: $0** (Supabase free tier).
**Tiempo: ~20 min de setup, después es 100% automático.**

---

## Arquitectura

```
iPhone notifica compra Santander
    ↓ (Continuity → espejo automático)
Mac recibe notificación
    ↓ macOS Notification DB (SQLite local)
Script Python lee cada 5 min vía launchd
    ↓ HTTPS POST
Supabase Edge Function /notification_ingest
    ↓ parsea texto Santander
    ↓ inserta a notification_inbox + santander_gastos
Dashboard ve gasto en tiempo real
    ↓
Mes siguiente: PDF Santander llega
    ↓ reconcile_notifications.py corre diariamente
    ↓ matchea PDF vs notificaciones
    ↓ borra duplicados preliminares
```

**¿Por qué no iOS Shortcuts directo?** Apple no expone "al recibir notificación" como trigger nativo. La forma confiable es leer las notificaciones en tu Mac (que tú dijiste que ya las recibe vía Continuity).

---

## Paso 1 — SQL en Supabase (2 min)

1. Supabase Dashboard → **SQL Editor**
2. Ejecutar el contenido completo de `intelligence/notifications_schema.sql`

Verifica: **Table Editor** → debe aparecer `notification_inbox`.

---

## Paso 2 — Token secreto (1 min)

```bash
openssl rand -hex 32
```
Guarda el output (64 caracteres). Lo usarás en el Mac y en Supabase.

---

## Paso 3 — Supabase CLI + deploy Edge Function (5 min)

```bash
# Instalar CLI
brew install supabase/tap/supabase
supabase login

# Linkear proyecto (project-ref está en la URL de Supabase Dashboard)
cd ~/Documents/Claude/FinancialDashboard
supabase link --project-ref TU_PROJECT_REF

# Setear el secreto en Supabase
supabase secrets set NOTIFICATION_TOKEN=tu_token_del_paso_2

# Deploy
supabase functions deploy notification_ingest --no-verify-jwt
```

Te dará una URL: `https://TU_PROJECT_REF.supabase.co/functions/v1/notification_ingest`

**Test desde terminal:**
```bash
curl -X POST https://TU_PROJECT_REF.supabase.co/functions/v1/notification_ingest \
  -H "Authorization: Bearer tu_token_del_paso_2" \
  -H "Content-Type: application/json" \
  -d '{"text": "Compra Visa Crédito por $25.500 en STARBUCKS COFFEE"}'
```

Debe responder `{"ok": true, "parsed": true, ...}`. Si lo hace, **media batalla ganada**.

---

## Paso 4 — Permisos en Mac (2 min)

El script lee `~/Library/Group Containers/group.com.apple.usernoted/db2/db` que macOS protege.

1. **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Botón **+** → agregar `Terminal.app` (o iTerm si usas iTerm)
3. Reinicia el terminal

---

## Paso 5 — Variables de entorno en `.env` (1 min)

Agrega a tu `.env` local:

```bash
NOTIFICATION_INGEST_URL=https://TU_PROJECT_REF.supabase.co/functions/v1/notification_ingest
NOTIFICATION_TOKEN=tu_token_del_paso_2
```

---

## Paso 6 — Probar el reader manualmente (2 min)

Genera una compra de prueba (cualquier cobro mínimo en Santander, o espera a una real). Después:

```bash
source venv/bin/activate
python -m intelligence.mac_notification_reader --since 24h --dry-run
```

Debería listar las notificaciones de Santander que encontró. Si todo OK:

```bash
python -m intelligence.mac_notification_reader --since 24h
```

→ Las envía a Supabase. Verifica en **Table Editor** → `notification_inbox` y `santander_gastos` (filtra `fuente='notification_iphone'`).

---

## Paso 7 — Automatizar con launchd cada 5 min (3 min)

Crea `~/Library/LaunchAgents/com.financial.notification.reader.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.financial.notification.reader</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /Users/matiasmollerv/Documents/Claude/FinancialDashboard && source venv/bin/activate && python -m intelligence.mac_notification_reader --since 30m</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/Users/matiasmollerv/Documents/Claude/FinancialDashboard/logs/notif_reader.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/matiasmollerv/Documents/Claude/FinancialDashboard/logs/notif_reader.err</string>
</dict>
</plist>
```

Activar:
```bash
launchctl load ~/Library/LaunchAgents/com.financial.notification.reader.plist
```

Verificar que esté corriendo:
```bash
launchctl list | grep financial.notification
```

---

## 🔄 Reconciliación automática

Ya está conectado al workflow diario de GitHub Actions:

1. Carga PDF Santander → `santander_gastos` con `fuente=null`
2. Corre `reconcile_notifications.py`
3. Matchea: mismo monto + moneda + fecha ±3d + merchant similar (fuzzy)
4. Borra entrada preliminar de notificación; deja la del PDF.

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| `No se pudo leer la tabla 'record'` | Faltan permisos. Full Disk Access en Terminal. |
| `unauthorized` en curl | El token del header no coincide con `supabase secrets list`. |
| `parsed: false` | El parser no reconoció el formato. Revisa `notification_inbox.raw_text` y mándame el ejemplo. |
| El reader no encuentra nada | Verifica el bundle ID exacto: en `mac_notification_reader.py` ajusta `SANTANDER_BUNDLE_HINTS`. Para descubrirlo, descomenta una línea de debug. |
| Gastos duplicados (notif + PDF) | Espera a que corra `reconcile_notifications.py` (8am Chile). O ejecútalo manualmente. |

---

## Comandos útiles

```bash
# Ver últimas notificaciones recibidas en BD
python -c "from database.supabase_client import get_client; \
  r = get_client().table('notification_inbox').select('*').order('fecha_recibido', desc=True).limit(5).execute(); \
  [print(row['fecha_recibido'], row['parsed_descripcion'], row['parsed_monto']) for row in r.data]"

# Reconciliar manualmente
python -m intelligence.reconcile_notifications --dry-run

# Re-deploy de la Edge Function (si cambias el parser)
supabase functions deploy notification_ingest --no-verify-jwt

# Ver logs del launchd job
tail -f logs/notif_reader.log
```
