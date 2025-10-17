import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const TXT_POS = {
  dni: { start: 25, end: 33 },
  nombre: { start: 40, end: 85 },
  referencia: { start: 115, end: 126 },
  importe: { start: 186, end: 195 },
};

const MULT = 2;
const ESTADO = "rechazada";

function sliceFixed(line: string, start: number, end: number): string {
  if (!line) return "";
  const idx = Math.max(0, start - 1);
  return idx < line.length ? line.slice(idx, end).trim() : "";
}

function parseAmount(raw: string): number {
  if (!raw) return 0.0;
  let s = raw.replace(/[^\d,.-]/g, "");
  
  if (s.includes(".") && s.includes(",")) {
    s = s.replace(/\./g, "").replace(/,/g, ".");
  } else if (s.includes(",")) {
    s = s.replace(/,/g, ".");
  }
  
  const parts = s.split(".");
  if (parts.length > 2) {
    s = parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
  }
  
  try {
    return parseFloat(s) || 0.0;
  } catch {
    return 0.0;
  }
}

async function extractRegistrosFromPdf(pdfBuffer: Uint8Array): Promise<number[]> {
  // Convertir PDF a texto usando una API simple de extracción
  const pdfText = new TextDecoder().decode(pdfBuffer);
  const regex = /Registro\s+(\d{1,5})/g;
  const matches = [...pdfText.matchAll(regex)];
  const registros = Array.from(new Set(matches.map(m => parseInt(m[1]))));
  return registros.sort((a, b) => a - b);
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const formData = await req.formData();
    const pdfFile = formData.get('pdf') as File;
    const txtFile = formData.get('txt') as File;
    const code = formData.get('code') as string;
    const desc = formData.get('desc') as string;

    if (!pdfFile || !txtFile) {
      throw new Error('Missing files');
    }

    console.log('Processing PRE BCP-txt...');

    const pdfBuffer = new Uint8Array(await pdfFile.arrayBuffer());
    const txtContent = await txtFile.text();
    const lines = txtContent.split('\n');

    const registros = await extractRegistrosFromPdf(pdfBuffer);
    const indices = registros.map(r => r * MULT).sort((a, b) => a - b);

    const rows = [];
    for (const i of indices) {
      if (i >= 1 && i <= lines.length) {
        const ln = lines[i - 1];
        const dni = sliceFixed(ln, TXT_POS.dni.start, TXT_POS.dni.end);
        const nombre = sliceFixed(ln, TXT_POS.nombre.start, TXT_POS.nombre.end);
        const ref = sliceFixed(ln, TXT_POS.referencia.start, TXT_POS.referencia.end);
        const impStr = sliceFixed(ln, TXT_POS.importe.start, TXT_POS.importe.end);
        const imp = parseAmount(impStr);

        rows.push({
          "dni/cex": dni,
          nombre: nombre,
          importe: imp,
          Referencia: ref,
          Estado: ESTADO,
          "Codigo de Rechazo": code,
          "Descripcion de Rechazo": desc,
        });
      }
    }

    const totalTransactions = rows.length;
    const totalAmount = rows.reduce((sum, row) => sum + row.importe, 0);

    console.log(`Processed ${totalTransactions} transactions, total: ${totalAmount}`);

    return new Response(
      JSON.stringify({
        results: rows,
        totalTransactions,
        totalAmount,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    console.error('Error processing PRE BCP-txt:', error);
    const message = error instanceof Error ? error.message : 'Unknown error';
    return new Response(
      JSON.stringify({ error: message }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
