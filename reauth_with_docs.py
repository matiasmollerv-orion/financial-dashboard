"""
Re-autentica con Gmail + Google Docs scopes y guarda el token.
Corre una vez manualmente: python3 reauth_with_docs.py
"""
import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/documents.readonly',
]

CREDENTIALS_FILE = 'config/credentials.json'
TOKEN_FILE = 'config/token.pickle'

def main():
    creds = None

    # Cargar token existente si hay
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    # Si no es válido o no tiene los scopes correctos, re-autenticar
    needs_reauth = (
        not creds or
        not creds.valid or
        not all(s in (creds.scopes or []) for s in SCOPES)
    )

    if needs_reauth:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Verificar que tenga los scopes nuevos
                if not all(s in (creds.scopes or []) for s in SCOPES):
                    raise Exception("Scopes insuficientes, re-auth completo necesario")
            except Exception as e:
                print(f"Refresh falló ({e}), iniciando flujo OAuth...")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
        print("✅ Token guardado con scopes:", creds.scopes)
    else:
        print("✅ Token ya válido con scopes:", creds.scopes)

    # Test rápido: leer el Google Doc
    from googleapiclient.discovery import build
    service = build('docs', 'v1', credentials=creds)
    doc_id = '12y_c_Q88VSHboL36rlwFgTmraQpYlktM40LJBgX0YHA'
    doc = service.documents().get(documentId=doc_id).execute()
    print(f"✅ Doc leído: '{doc.get('title')}'")

if __name__ == '__main__':
    main()
