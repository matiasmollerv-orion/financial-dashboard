#!/usr/bin/env python3
"""
Busca newsletters nuevas en Gmail (últimas 2 semanas) y emails "brain:" (inbox
desde el celular), extrae el contenido y los captura en GBrain via CLI.

Fuentes de newsletters definidas en NEWSLETTER_SOURCES.
Emails con asunto que empieza con "brain:" se capturan bajo inbox/.
"""

import base64
import pickle
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TOKEN_PATH = SCRIPT_DIR / "config" / "token.pickle"
GBRAIN_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")

MAX_CONTENT_CHARS = 60_000  # emails muy largos se truncan

# query Gmail -> prefijo de slug en el brain
NEWSLETTER_SOURCES = [
    ("from:strategybreakdowns newer_than:14d", "newsletters/strategy-breakdowns"),
    ("from:elena newer_than:14d", "newsletters/elena-verna"),
    ("from:revolution newer_than:14d", "newsletters/revolution"),
    ("from:mckinsey newer_than:14d", "newsletters/mckinsey"),
    ("from:chamath newer_than:14d", "newsletters/chamath"),
]

BRAIN_INBOX_QUERY = "subject:brain newer_than:14d"

# Links de YouTube en emails "brain:" → se baja la transcripción (subtítulos
# públicos del video, gratis, sin API key; librería youtube-transcript-api).
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})"
)


def youtube_transcripts(text):
    """Transcripciones de los videos de YouTube linkeados en el texto."""
    out = []
    for vid in dict.fromkeys(YOUTUBE_RE.findall(text)):  # únicos, en orden
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            langs = ["es", "es-419", "es-ES", "en"]
            try:
                segs = YouTubeTranscriptApi().fetch(vid, languages=langs)
                txt = " ".join(s.text for s in segs)
            except AttributeError:  # API antigua (<1.0)
                segs = YouTubeTranscriptApi.get_transcript(vid, languages=langs)
                txt = " ".join(s["text"] for s in segs)
            out.append(f"\n\n## Transcripción YouTube ({vid})\n\n{txt[:40_000]}")
            print(f"    + transcripción {vid} ({len(txt)} chars)")
        except Exception as e:  # sin subtítulos, video privado, etc.
            print(f"    (sin transcripción {vid}: {type(e).__name__} {repr(e)[:120]})")
    return "".join(out)


class _HTMLToText(HTMLParser):
    SKIP_TAGS = {"style", "script", "head", "title"}
    BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        # colapsar espacios y líneas en blanco múltiples
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html):
    parser = _HTMLToText()
    parser.feed(html)
    return parser.text()


def slugify(text, max_len=60):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:max_len].rstrip("-") or "sin-titulo"


def get_gmail_service():
    from googleapiclient.discovery import build

    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    return build("gmail", "v1", credentials=creds)


def _decode_part(part):
    data = part.get("body", {}).get("data")
    if not data:
        return None
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def extract_body(payload):
    """Devuelve texto plano del mensaje, prefiriendo text/plain sobre text/html."""
    plain, html = None, None
    stack = [payload]
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        if mime == "text/plain" and plain is None:
            plain = _decode_part(part)
        elif mime == "text/html" and html is None:
            html = _decode_part(part)
        stack.extend(part.get("parts", []))

    if plain and plain.strip():
        return plain.strip()
    if html:
        return html_to_text(html)
    return ""


def get_header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def gbrain_put(slug, content):
    result = subprocess.run(
        [GBRAIN_BIN, "put", slug],
        input=content,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gbrain put {slug} failed (exit {result.returncode}): {result.stderr.strip()}"
        )


def build_page(subject, sender, date, body):
    return (
        f"# {subject}\n\n"
        f"- **De:** {sender}\n"
        f"- **Fecha:** {date}\n"
        f"- **Capturado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"---\n\n{body[:MAX_CONTENT_CHARS]}"
    )


def process_messages(service, query, slug_fn, label):
    resp = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = resp.get("messages", [])
    print(f"[{label}] query={query!r} -> {len(messages)} mensajes")

    captured = 0
    for m in messages:
        msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        subject = get_header(msg, "Subject") or "(sin asunto)"
        sender = get_header(msg, "From")
        date = get_header(msg, "Date")

        body = extract_body(msg.get("payload", {}))
        if not body.strip():
            print(f"  SKIP (cuerpo vacío): {subject}")
            continue

        slug = slug_fn(subject)
        try:
            gbrain_put(slug, build_page(subject, sender, date, body))
            print(f"  OK  {slug}  ({len(body)} chars)  «{subject}»")
            captured += 1
        except RuntimeError as e:
            print(f"  ERROR {slug}: {e}", file=sys.stderr)
    return captured


def main():
    service = get_gmail_service()
    total = 0

    for query, prefix in NEWSLETTER_SOURCES:
        total += process_messages(
            service, query,
            slug_fn=lambda subj, p=prefix: f"{p}-{slugify(subj)}",
            label=prefix,
        )

    # Inbox desde el celular: asunto "brain: lo que sea" (acepta "Re: brain:"
    # — responderse a sí mismo agrega contenido a la misma página)
    def brain_slug(subject):
        clean = re.sub(r"^\s*(re:\s*)*brain:\s*", "", subject, flags=re.IGNORECASE)
        return f"inbox/{slugify(clean)}"

    # filtrar solo asuntos que realmente empiezan con "brain:" (o "Re: brain:")
    resp = service.users().messages().list(
        userId="me", q=BRAIN_INBOX_QUERY, maxResults=20
    ).execute()
    brain_msgs = []
    for m in resp.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["Subject"],
        ).execute()
        if re.match(r"^\s*(re:\s*)*brain:", get_header(msg, "Subject"), flags=re.IGNORECASE):
            brain_msgs.append(m["id"])

    print(f"[inbox brain:] {len(brain_msgs)} mensajes con prefijo válido")
    # Gmail lista más-nuevo-primero; procesar al revés para que ante asuntos
    # repetidos (ej: "Re: brain: X") el mensaje MÁS NUEVO quede en la página.
    for mid in reversed(brain_msgs):
        msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
        subject = get_header(msg, "Subject")
        body = extract_body(msg.get("payload", {}))
        # Links de YouTube (en asunto o cuerpo) → agrega la transcripción.
        # Un email cuyo único contenido es el link ya no queda vacío.
        extra = youtube_transcripts(f"{subject}\n{body}")
        if not (body.strip() or extra):
            print(f"  SKIP (cuerpo vacío): {subject}")
            continue
        body = body + extra
        slug = brain_slug(subject)
        try:
            gbrain_put(slug, build_page(subject, get_header(msg, "From"), get_header(msg, "Date"), body))
            print(f"  OK  {slug}  «{subject}»")
            total += 1
        except RuntimeError as e:
            print(f"  ERROR {slug}: {e}", file=sys.stderr)

    print(f"\nTotal capturado: {total} páginas")


if __name__ == "__main__":
    main()
