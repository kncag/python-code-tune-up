import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { decompress } from "https://deno.land/x/zip@v1.2.5/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ESTADO = "rechazada";

const KEYWORDS_NO_TIT = [
  "no es titular",
  "beneficiario no",
  "cliente no titular",
  "no titular",
  "continuar",
  "puedes continuar",
  "si deseas, puedes continuar",
];

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

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const formData = await req.formData();
    const zipFile = formData.get('zip') as File;

    if (!zipFile) {
      throw new Error('Missing ZIP file');
    }

    console.log('Processing Rechazo IBK...');

    const XLSX = await import('https://cdn.sheetjs.com/xlsx-0.20.1/package/xlsx.mjs');
    
    const zipBuffer = new Uint8Array(await zipFile.arrayBuffer());
    
    // Guardar temporalmente el archivo ZIP
    const tempPath = await Deno.makeTempFile({ suffix: '.zip' });
    await Deno.writeFile(tempPath, zipBuffer);
    
    // Descomprimir
    const tempDir = await Deno.makeTempDir();
    await decompress(tempPath, tempDir);
    
    // Buscar el archivo Excel dentro del ZIP
    let excelPath = '';
    for await (const entry of Deno.readDir(tempDir)) {
      if (entry.isFile && (entry.name.endsWith('.xlsx') || entry.name.endsWith('.xls'))) {
        excelPath = `${tempDir}/${entry.name}`;
        break;
      }
    }

    if (!excelPath) {
      throw new Error('No Excel file found in ZIP');
    }

    const excelBuffer = await Deno.readFile(excelPath);
    const workbook = XLSX.read(excelBuffer);
    const worksheet = workbook.Sheets[workbook.SheetNames[0]];
    const data: any[] = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' });

    // Procesar desde la fila 11 (índice 11)
    const dataFrom11 = data.slice(11);

    // Filtrar solo las filas que tienen valor en la columna O (índice 14)
    const validRows = dataFrom11.filter((row: any[]) => {
      const colO = row[14];
      return colO !== null && colO !== undefined && String(colO).trim() !== '';
    });

    const rows = validRows.map((row: any[]) => {
      const situacion = String(row[14] || '').toLowerCase();
      const isNoTitular = KEYWORDS_NO_TIT.some(kw => situacion.includes(kw));

      return {
        "dni/cex": String(row[4] || ''),
        nombre: String(row[5] || ''),
        importe: parseAmount(row[13]),
        Referencia: String(row[7] || ''),
        Estado: ESTADO,
        "Codigo de Rechazo": isNoTitular ? "R016" : "R002",
        "Descripcion de Rechazo": isNoTitular ? "CLIENTE NO TITULAR DE LA CUENTA" : "CUENTA INVALIDA",
      };
    });

    const totalTransactions = rows.length;
    const totalAmount = rows.reduce((sum, row) => sum + row.importe, 0);

    // Limpiar archivos temporales
    await Deno.remove(tempPath);
    await Deno.remove(tempDir, { recursive: true });

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
    console.error('Error processing Rechazo IBK:', error);
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
