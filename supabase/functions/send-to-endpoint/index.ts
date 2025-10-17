import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const ENDPOINT = "https://q6caqnpy09.execute-api.us-east-1.amazonaws.com/OPS/kpayout/v1/payout_process/reject_invoices_batch";

const SUBSET_COLS = [
  "Referencia",
  "Estado",
  "Codigo de Rechazo",
  "Descripcion de Rechazo",
];

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { data } = await req.json();

    if (!data || !Array.isArray(data)) {
      throw new Error('Invalid data format');
    }

    console.log('Sending data to endpoint...');

    const XLSX = await import('https://cdn.sheetjs.com/xlsx-0.20.1/package/xlsx.mjs');
    
    // Filtrar solo las columnas requeridas
    const filteredData = data.map((row: any) => {
      const filtered: any = {};
      SUBSET_COLS.forEach(col => {
        filtered[col] = row[col];
      });
      return filtered;
    });

    // Generar Excel
    const worksheet = XLSX.utils.json_to_sheet(filteredData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Rechazos');
    const excelBuffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });

    // Crear FormData para el POST
    const formData = new FormData();
    const blob = new Blob([excelBuffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    formData.append('edt', blob, 'rechazos.xlsx');

    // Enviar al endpoint
    const response = await fetch(ENDPOINT, {
      method: 'POST',
      body: formData,
    });

    const responseText = await response.text();

    console.log(`Endpoint response: ${response.status} - ${responseText}`);

    return new Response(
      JSON.stringify({
        status: response.status,
        message: responseText,
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    console.error('Error sending to endpoint:', error);
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
