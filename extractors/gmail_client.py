# ============================================================
# GMAIL CLIENT — Implementación IMAP (sin OAuth, sin tokens que expiran)
#
# Usa imap.gmail.com con App Password. App Passwords NO expiran
# salvo que cambies password de Google o los revoques manualmente.
#
# Requisitos:
#   - GMAIL_USER en .env (ej. matiasmollerv@gmail.com)
#   - GMAIL_APP_PASSWORD en .env (16 chars, mismo que ya usamos para SMTP)
#   - 2-Step Verification ON en la cuenta Google
#
# Diseñado para mantener compatibilidad con el código existente
# que esperaba la API de Gmail (search_emails, get_email_detail, etc).
# ============================================================

import os
import re
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_DIR  = BASE_DIR / "config"
DATA_DIR    = BASE_DIR / "data" / "raw"


# ── IMAP SERVICE WRAPPER ─────────────────────────────────────
class GmailIMAPService:
    """
    Wrapper sobre imaplib que expone una API similar a la antigua Gmail API.
    De este modo, search_emails / get_email_detail / etc. siguen funcionando
    con la misma firma sin tener que modificar los parsers existentes.
    """

    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self.conn = None
        self._message_cache = {}   # cache UID → email.Message para evitar re-fetches
        self._connect()

    def _connect(self):
        self.conn = imaplib.IMAP4_SSL(self.host, 993)
        self.conn.login(self.user, self.password)
        # Seleccionar todos los emails (incluyendo archived). Gmail mapea
        # "[Gmail]/All Mail" o "[Gmail]/Todos" según el idioma de la cuenta.
        for box in ('"[Gmail]/All Mail"', '"[Gmail]/Todos"', "INBOX"):
            typ, _ = self.conn.select(box, readonly=True)
            if typ == "OK":
                self.selected_box = box
                break

    def close(self):
        try:
            self.conn.close()
            self.conn.logout()
        except Exception:
            pass

    def search(self, criteria: str):
        """Retorna lista de UIDs. Normaliza acentos (Gmail IMAP no soporta UTF-8 en SEARCH)."""
        # Gmail IMAP rechaza queries con caracteres no-ASCII.
        # Normalizamos: "Crédito" → "Credito". Gmail indexa sin acentos
        # así que la búsqueda funciona igual.
        import unicodedata
        normalized = unicodedata.normalize("NFKD", criteria).encode("ascii", "ignore").decode("ascii")

        try:
            typ, data = self.conn.search(None, normalized)
        except imaplib.IMAP4.error:
            return []

        if typ != "OK":
            return []
        return data[0].split() if data and data[0] else []

    def fetch_message(self, uid: bytes):
        """Retorna email.Message para un UID. Cachea para no re-fetchar."""
        uid_key = uid.decode() if isinstance(uid, bytes) else uid
        if uid_key in self._message_cache:
            return self._message_cache[uid_key]
        typ, data = self.conn.fetch(uid, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            return None
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        self._message_cache[uid_key] = msg
        return msg


# ── CONSTRUCTOR PÚBLICO ──────────────────────────────────────
def get_gmail_service():
    """
    Reemplaza la antigua get_gmail_service() basada en OAuth.
    Usa GMAIL_USER y GMAIL_APP_PASSWORD del entorno.
    """
    user = os.getenv("GMAIL_USER", "").strip()
    pwd  = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")

    if not user or not pwd:
        raise RuntimeError(
            "Faltan GMAIL_USER y/o GMAIL_APP_PASSWORD en .env. "
            "Genera un App Password en https://myaccount.google.com/apppasswords"
        )

    return GmailIMAPService("imap.gmail.com", user, pwd)


# ── TRADUCTOR Gmail-query → IMAP-criteria ───────────────────
_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def _to_imap_date(yyyy_mm_dd: str) -> str:
    """Convierte 2026/05/15 o 2026-05-15 a 15-May-2026 (formato IMAP)."""
    parts = re.split(r"[-/]", yyyy_mm_dd)
    if len(parts) != 3:
        return yyyy_mm_dd
    y, m, d = parts
    return f"{int(d):02d}-{_MONTHS[int(m)-1]}-{int(y)}"


def _parse_gmail_query(q: str) -> str:
    """
    Traduce una query estilo Gmail a criterios IMAP.
    Soporta: from:, subject:, after:, before:, -subject: (negación).
    """
    if not q:
        return "ALL"

    criteria = []
    # Patrones a extraer (orden importa)
    patterns = [
        (r'from:(\S+)',                   lambda m: f'FROM "{m.group(1)}"'),
        (r'-subject:"([^"]+)"',           lambda m: f'NOT SUBJECT "{m.group(1)}"'),
        (r'-subject:(\S+)',               lambda m: f'NOT SUBJECT "{m.group(1)}"'),
        (r'subject:"([^"]+)"',            lambda m: f'SUBJECT "{m.group(1)}"'),
        (r'subject:(\S+)',                lambda m: f'SUBJECT "{m.group(1)}"'),
        (r'after:(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  lambda m: f'SINCE {_to_imap_date(m.group(1))}'),
        (r'before:(\d{4}[-/]\d{1,2}[-/]\d{1,2})', lambda m: f'BEFORE {_to_imap_date(m.group(1))}'),
    ]

    remaining = q
    for pat, builder in patterns:
        for m in re.finditer(pat, remaining):
            criteria.append(builder(m))
        remaining = re.sub(pat, "", remaining)

    # Lo que quedó del query → como TEXT search (texto libre)
    free_text = remaining.strip()
    if free_text:
        # Quitar espacios múltiples
        free_text = re.sub(r"\s+", " ", free_text).strip()
        if free_text:
            criteria.append(f'TEXT "{free_text}"')

    if not criteria:
        return "ALL"

    # IMAP usa AND implícito cuando van pegados
    return " ".join(criteria)


# ── API COMPATIBLE CON EL CÓDIGO EXISTENTE ──────────────────
def search_emails(service: GmailIMAPService, query: str, max_results: int = 50) -> list:
    """
    Busca correos. Retorna lista de dicts con 'id' (UID IMAP).
    Compatible con la firma anterior de Gmail API.
    """
    criteria = _parse_gmail_query(query)
    uids = service.search(criteria)
    # Más recientes primero
    uids = list(reversed(uids))
    if max_results and len(uids) > max_results:
        uids = uids[:max_results]
    return [{"id": uid.decode() if isinstance(uid, bytes) else str(uid)} for uid in uids]


def get_email_detail(service: GmailIMAPService, msg_id: str) -> dict:
    """
    Retorna un dict con formato similar al de Gmail API para mantener
    compatibilidad. Estructura:
      {
        "id": "<uid>",
        "_msg": <email.Message>,   # objeto real para uso interno
        "payload": {
          "headers": [{"name":..., "value":...}, ...],
          "parts": [...],         # representación simplificada para get_email_body
        }
      }
    """
    uid = msg_id.encode() if isinstance(msg_id, str) else msg_id
    msg = service.fetch_message(uid)
    if msg is None:
        return {"id": msg_id, "_msg": None, "payload": {"headers": [], "parts": []}}

    # Construir headers
    headers = []
    for k, v in msg.items():
        headers.append({"name": k, "value": _decode_header_value(v)})

    return {
        "id": msg_id,
        "_msg": msg,
        "payload": {
            "headers": headers,
            "parts": [],  # los parsers usan get_email_body() para procesar
        },
    }


def _decode_header_value(value: str) -> str:
    """Decodifica headers que pueden estar en encoded-word (=?utf-8?B?...?=)."""
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try:
                out += txt.decode(enc or "utf-8", errors="ignore")
            except Exception:
                out += txt.decode("utf-8", errors="ignore")
        else:
            out += txt
    return out


def get_email_body(msg_dict: dict) -> str:
    """
    Extrae cuerpo text/plain (con fallback a HTML→texto plano simple).
    """
    msg = msg_dict.get("_msg")
    if msg is None:
        return ""

    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    text_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
            elif ctype == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            text_parts.append(payload.decode(msg.get_content_charset() or "utf-8", errors="ignore"))

    if text_parts:
        return "\n".join(text_parts)
    if html_parts:
        # Fallback: HTML simple → texto removiendo tags
        html = "\n".join(html_parts)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text
    return ""


def download_attachments(service: GmailIMAPService, msg_dict: dict, dest_folder: Path) -> list:
    """
    Descarga PDFs adjuntos a dest_folder. Retorna lista de paths.
    """
    msg = msg_dict.get("_msg")
    if msg is None:
        return []

    dest_folder.mkdir(parents=True, exist_ok=True)
    saved = []

    if not msg.is_multipart():
        return saved

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename() or ""
        # Decodificar filename si está encoded
        filename = _decode_header_value(filename)
        if not filename.lower().endswith(".pdf"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        out_path = dest_folder / filename
        with open(out_path, "wb") as f:
            f.write(payload)
        saved.append(out_path)
        print(f"  ✓ Descargado: {filename}")

    return saved


def get_email_subject(msg_dict: dict) -> str:
    msg = msg_dict.get("_msg")
    if msg is None:
        return ""
    return _decode_header_value(msg.get("Subject", ""))


def get_email_date(msg_dict: dict) -> str:
    """Retorna el header Date crudo (los parsers ya lo parsean)."""
    msg = msg_dict.get("_msg")
    if msg is None:
        return ""
    return msg.get("Date", "")
