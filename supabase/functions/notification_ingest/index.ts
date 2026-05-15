// ============================================================
// Edge Function: notification_ingest
//
// Recibe una notificación cruda del iPhone (vía iOS Shortcut),
// la parsea (formato Santander Chile), la guarda en
// notification_inbox y crea entrada preliminar en santander_gastos.
//
// Deploy:
//   supabase functions deploy notification_ingest --project-ref TU_REF
//
// Secrets (deben estar configurados con `supabase secrets set`):
//   NOTIFICATION_TOKEN     = string secreto que el iPhone envía como Bearer
//   SUPABASE_URL           = automático
//   SUPABASE_SERVICE_ROLE_KEY = para escribir a tablas
// ============================================================

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const SECRET_TOKEN = Deno.env.get("NOTIFICATION_TOKEN")!;

// ── Parser Santander Chile ──────────────────────────────────
interface Parsed {
  monto: number;
  moneda: "CLP" | "USD";
  descripcion: string;
  fecha?: string;        // YYYY-MM-DD
  source?: string;       // santander_tc / santander_cc
}

function parseSantander(rawText: string): { ok: boolean; data?: Parsed; reason?: string } {
  const text = rawText.replace(/\s+/g, " ").trim();
  if (!text) return { ok: false, reason: "empty" };

  // Detección de moneda y monto
  // Patrones que cubren mayoría de notificaciones Santander:
  //   "Compra Visa por $25.500 en STARBUCKS"
  //   "Compra US$49.99 en NETFLIX"
  //   "Cargo de $1.234.567 en ..."
  //   "Aprobado por $X.XXX en MERCHANT"
  let monto: number | null = null;
  let moneda: "CLP" | "USD" = "CLP";

  // 1. USD primero (más específico)
  const usd = text.match(/US\$\s*([\d.,]+)/i);
  if (usd) {
    const num = usd[1].replace(/,/g, ".");
    // Si tiene una sola coma/punto, asumimos decimales
    monto = parseFloat(num);
    moneda = "USD";
  } else {
    // CLP: $X.XXX o $X.XXX.XXX  (puntos son miles, no decimales)
    const clp = text.match(/\$\s*([\d.]+)(?:[\s\,]|$)/);
    if (clp) {
      monto = parseInt(clp[1].replace(/\./g, ""), 10);
      moneda = "CLP";
    }
  }

  if (!monto || isNaN(monto)) return { ok: false, reason: "no_monto" };

  // Extraer merchant: típicamente después de " en "
  let descripcion = "";
  const enMatch = text.match(/\s+en\s+(.+?)(?:\s*(?:hoy|ayer|el\s|a\s|\.|$))/i);
  if (enMatch) {
    descripcion = enMatch[1].trim().toUpperCase();
  } else {
    // Fallback: todo después del monto
    const after = text.split(/\$|US\$/).pop() || "";
    descripcion = after.replace(/^\s*[\d.,]+\s*/, "").trim().toUpperCase();
  }

  // Limitar largo y limpiar
  descripcion = descripcion.replace(/[^\w\sÁÉÍÓÚÑáéíóúñ&\-.*]/g, " ").replace(/\s+/g, " ").trim().slice(0, 100);

  if (!descripcion) return { ok: false, reason: "no_merchant" };

  // Source heurístico
  let source = "santander_tc";  // default
  if (/cuenta corriente|transfer|abono|deposito/i.test(text)) source = "santander_cc";

  return {
    ok: true,
    data: {
      monto,
      moneda,
      descripcion,
      fecha: new Date().toISOString().slice(0, 10),
      source,
    },
  };
}


// ── Handler HTTP ────────────────────────────────────────────
serve(async (req) => {
  // Solo POST
  if (req.method !== "POST") {
    return jsonResp({ ok: false, error: "method_not_allowed" }, 405);
  }

  // Auth: Bearer token
  const auth = req.headers.get("authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : auth;
  if (!SECRET_TOKEN || token !== SECRET_TOKEN) {
    return jsonResp({ ok: false, error: "unauthorized" }, 401);
  }

  // Body
  let body: any;
  try {
    body = await req.json();
  } catch {
    // Aceptar también text/plain
    try {
      const txt = await req.text();
      body = { text: txt };
    } catch {
      return jsonResp({ ok: false, error: "bad_request" }, 400);
    }
  }

  const rawText: string = (body.text || body.message || body.body || "").toString();
  const sourceHint: string | undefined = body.source;

  if (!rawText) {
    return jsonResp({ ok: false, error: "missing_text" }, 400);
  }

  const sb = createClient(SUPABASE_URL, SERVICE_KEY);

  // Parse
  const parsed = parseSantander(rawText);

  // Insertar en notification_inbox (siempre, parseable o no — sirve de auditoría)
  const inboxRow: any = {
    raw_text: rawText.slice(0, 5000),
    source: parsed.data?.source || sourceHint || null,
    parsed_monto: parsed.data?.monto ?? null,
    parsed_descripcion: parsed.data?.descripcion ?? null,
    parsed_moneda: parsed.data?.moneda ?? null,
    parse_error: parsed.ok ? null : parsed.reason,
    procesado: parsed.ok,
    user_agent: req.headers.get("user-agent") || null,
    ip: req.headers.get("x-forwarded-for") || null,
  };

  const { data: inboxIns, error: inboxErr } = await sb
    .from("notification_inbox")
    .insert(inboxRow)
    .select("id")
    .single();

  if (inboxErr) {
    return jsonResp({ ok: false, error: "db_inbox_failed", detail: inboxErr.message }, 500);
  }

  // Si no se pudo parsear, devolvemos OK (la fila quedó en inbox para revisar)
  if (!parsed.ok || !parsed.data) {
    return jsonResp({
      ok: true,
      parsed: false,
      inbox_id: inboxIns?.id,
      reason: parsed.reason,
      hint: "Revisa la fila en notification_inbox y mejora el parser si es necesario."
    });
  }

  // Si se parseó OK → también insertamos a santander_gastos (preliminar)
  const gastoRow = {
    fecha: parsed.data.fecha!,
    descripcion: parsed.data.descripcion,
    monto: parsed.data.monto,
    moneda: parsed.data.moneda,
    fuente: "notification_iphone",
  };

  const { data: gastoIns, error: gastoErr } = await sb
    .from("santander_gastos")
    .insert(gastoRow)
    .select("id")
    .single();

  if (gastoErr) {
    return jsonResp({
      ok: false,
      error: "db_gasto_failed",
      detail: gastoErr.message,
      inbox_id: inboxIns?.id,
    }, 500);
  }

  // Linkear inbox con gasto
  await sb
    .from("notification_inbox")
    .update({ gasto_id: gastoIns?.id })
    .eq("id", inboxIns?.id);

  return jsonResp({
    ok: true,
    parsed: true,
    inbox_id: inboxIns?.id,
    gasto_id: gastoIns?.id,
    data: parsed.data,
  });
});


function jsonResp(body: any, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
