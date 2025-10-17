import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ESTADO = "rechazada";

function parseAmount(raw: any): number {
  if (raw === null || raw === undefined) return 0.0;
  const s = String(raw).replace(/[^\d,.-]/g, "");
  
  let cleaned = s;
  if (s.includes(".") && s.includes(",")) {
    cleaned = s.replace(/\./g, "").replace(/,/g, ".");
  } else if (s.includes(",")) {
    cleaned = s.replace(/,/g, ".");
  }
  
  const parts = cleaned.split(".");
  if (parts.length > 2) {
    cleaned = parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
  }
  
  try {
    return parseFloat(cleaned) || 0.0;
  } catch {
    return 0.0;
  }
}

async function extractRowNumbersFromPdf(pdfBuffer: Uint8Array): Promise<number[]> {
  const pdfText = new TextDecoder().decode(pdfBuffer);
  const regex = /Registro\s+(\d+)/g;
  const matches = [...pdfText.matchAll(regex)];
  const rowNumbers = Array.from(new Set(matches.map(m => parseInt(m[1]) + 1)));
  return rowNumbers.sort((a, b) => a - b);
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const formData = await req.formData();
    const pdfFile = formData.get('pdf') as File;
    const excelFile = formData.get('excel') as File;
    const code = formData.get('code') as string;
    const desc = formData.get('desc') as string;

    if (!pdfFile || !excelFile) {
      throw new Error('Missing files');
    }

    console.log('Processing PRE BCP-xlsx...');

    // Importar la biblioteca xlsx
    const XLSX = await import('https://cdn.sheetjs.com/xlsx-0.20.1/package/xlsx.mjs');
    
    const pdfBuffer = new Uint8Array(await pdfFile.arrayBuffer());
    const excelBuffer = await excelFile.arrayBuffer();
    
    const rowNumbers = await extractRowNumbersFromPdf(pdfBuffer);
    
    const workbook = XLSX.read(excelBuffer);
    const worksheet = workbook.Sheets[workbook.SheetNames[0]];
    const data: any[] = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' });

    const validRows = rowNumbers.filter(i => i >= 0 && i < data.length);
    const selectedData = validRows.map(i => data[i]);

    const rows = selectedData.map((row: any[]) => ({
      "dni/cex": String(row[0] || ''),
      nombre: String(row[3] || row[1] || ''),
      importe: parseAmount(row[12]),
      Referencia: String(row[7] || ''),
      Estado: ESTADO,
      "Codigo de Rechazo": code,
      "Descripcion de Rechazo": desc,
    }));

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
    console.error('Error processing PRE BCP-xlsx:', error);
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
