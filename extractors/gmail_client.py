# ============================================================
# GMAIL CLIENT
# Maneja autenticación OAuth y búsqueda de correos
# ============================================================

import os
import base64
import pickle
from pathlib import Path
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

# Permisos: solo lectura de Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_DIR  = BASE_DIR / "config"
DATA_DIR    = BASE_DIR / "data" / "raw"
TOKEN_FILE  = CONFIG_DIR / "token.pickle"
CREDS_FILE  = CONFIG_DIR / "credentials.json"


def get_gmail_service():
    """
    Retorna un servicio autenticado de Gmail.
    La primera vez abre el navegador para que autorices.
    Las siguientes veces usa el token guardado.
    """
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró credentials.json en {CREDS_FILE}\n"
                    "Descárgalo desde Google Cloud Console y guárdalo ahí."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


def search_emails(service, query: str, max_results: int = 50) -> list[dict]:
    """
    Busca correos en Gmail usando query estilo Gmail.
    Pagina automáticamente para obtener TODOS los resultados.
    Ejemplo: 'from:mensajeria@santander.cl subject:Estado de Cuenta'
    """
    messages = []
    page_token = None

    while True:
        params = {
            "userId": "me",
            "q": query,
            "maxResults": min(max_results, 500),  # Gmail permite máx 500 por página
        }
        if page_token:
            params["pageToken"] = page_token

        result = service.users().messages().list(**params).execute()
        batch = result.get("messages", [])
        messages.extend(batch)

        # Si pedimos un límite específico y ya lo alcanzamos, parar
        if len(messages) >= max_results:
            messages = messages[:max_results]
            break

        # Si hay más páginas y no hay límite (max_results=9999), seguir
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return messages


def get_email_detail(service, msg_id: str) -> dict:
    """
    Retorna el detalle completo de un correo por su ID.
    """
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full"
    ).execute()
    return msg


def get_email_body(msg: dict) -> str:
    """
    Extrae el cuerpo en texto plano de un correo.
    """
    payload = msg.get("payload", {})
    body = ""

    def extract_parts(parts):
        text = ""
        for part in parts:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    text += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif "parts" in part:
                text += extract_parts(part["parts"])
        return text

    if "parts" in payload:
        body = extract_parts(payload["parts"])
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return body


def download_attachments(service, msg: dict, dest_folder: Path) -> list[Path]:
    """
    Descarga todos los PDFs adjuntos de un correo.
    Retorna lista de rutas de archivos guardados.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    saved = []
    payload = msg.get("payload", {})

    def process_parts(parts):
        for part in parts:
            filename = part.get("filename", "")
            if filename.lower().endswith(".pdf"):
                att_id = part.get("body", {}).get("attachmentId")
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId="me",
                        messageId=msg["id"],
                        id=att_id
                    ).execute()
                    data = base64.urlsafe_b64decode(att["data"])
                    out_path = dest_folder / filename
                    with open(out_path, "wb") as f:
                        f.write(data)
                    saved.append(out_path)
                    print(f"  ✓ Descargado: {filename}")
            if "parts" in part:
                process_parts(part["parts"])

    if "parts" in payload:
        process_parts(payload["parts"])

    return saved


def get_email_subject(msg: dict) -> str:
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == "subject":
            return h["value"]
    return ""


def get_email_date(msg: dict) -> str:
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == "date":
            return h["value"]
    return ""
