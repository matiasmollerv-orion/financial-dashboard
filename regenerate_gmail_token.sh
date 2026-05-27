#!/usr/bin/env bash
# ============================================================
# REGENERATE GMAIL TOKEN — script todo-en-uno
#
# 1. Borra el token expirado
# 2. Lanza flujo OAuth (te abre navegador)
# 3. Convierte el nuevo token a base64
# 4. Lo copia al clipboard listo para pegar en GitHub Secrets
# 5. Te da las instrucciones exactas
#
# Uso: ./regenerate_gmail_token.sh
# ============================================================

set -e
cd "$(dirname "$0")"

echo "🔑 Regenerando token Gmail..."
echo ""

# 1. Backup del token viejo (por si acaso)
if [ -f config/token.pickle ]; then
    cp config/token.pickle config/token.pickle.bak
    rm config/token.pickle
    echo "📦 Token viejo respaldado en config/token.pickle.bak"
fi

# 2. Activar venv
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

# 3. Lanzar OAuth flow (esto abrirá el navegador)
echo ""
echo "🌐 Abriendo navegador para autenticación..."
echo "    → Autentica con matiasmollerv@gmail.com"
echo "    → Si Google dice 'app no verificada', click 'Avanzado' → 'Ir a Financial Dashboard'"
echo ""
python -c "
import sys
sys.path.insert(0, '.')
from extractors.gmail_client import get_gmail_service
service = get_gmail_service()
# Probar que funciona
result = service.users().labels().list(userId='me').execute()
print(f'✅ Token regenerado. {len(result.get(\"labels\", []))} labels detectados.')
"

# 4. Verificar que el nuevo token se creó
if [ ! -f config/token.pickle ]; then
    echo "❌ ERROR: no se creó config/token.pickle. Revisa el flujo OAuth."
    exit 1
fi

# 5. Convertir a base64 y copiar al clipboard
TOKEN_B64=$(base64 -i config/token.pickle)
echo "$TOKEN_B64" | pbcopy

echo ""
echo "✅ Token regenerado exitosamente y copiado al clipboard."
echo ""
echo "=================================================="
echo "📋 PRÓXIMOS PASOS (importante):"
echo "=================================================="
echo ""
echo "1. Anda a:"
echo "   https://github.com/matiasmollerv-orion/financial-dashboard/settings/secrets/actions"
echo ""
echo "2. Edita el secret 'GMAIL_TOKEN_PICKLE'"
echo "   (o créalo si no existe)"
echo ""
echo "3. Pega el contenido (Cmd+V) que ya está en tu clipboard"
echo "   (es un string base64 largo)"
echo ""
echo "4. Click 'Update secret'"
echo ""
echo "5. Re-ejecuta el workflow manualmente:"
echo "   gh workflow run daily-update.yml"
echo ""
echo "6. Verifica que corra OK:"
echo "   gh run list --limit 1 --workflow=daily-update.yml"
echo ""
echo "=================================================="
echo ""
echo "💡 TIP: si esto se sigue rompiendo cada 7 días, la app NO está en Production."
echo "   Anda a https://console.cloud.google.com/apis/credentials/consent"
echo "   y confirma que 'Publishing status' diga 'In production' (NO 'Testing')."
echo ""
