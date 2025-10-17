import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";

interface ResultData {
  "dni/cex": string;
  nombre: string;
  importe: number;
  Referencia: string;
  Estado: string;
  "Codigo de Rechazo": string;
  "Descripcion de Rechazo": string;
}

interface ResultsTableProps {
  data: ResultData[];
  totalTransactions: number;
  totalAmount: number;
}

const ResultsTable = ({
  data,
  totalTransactions,
  totalAmount,
}: ResultsTableProps) => {
  const { toast } = useToast();

  const handleDownload = async () => {
    try {
      const { data: blob, error } = await supabase.functions.invoke(
        "generate-excel",
        {
          body: { data },
        }
      );

      if (error) throw error;

      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `rechazos_${Date.now()}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast({
        title: "Descarga exitosa",
        description: "El archivo Excel se ha descargado correctamente",
      });
    } catch (error) {
      toast({
        title: "Error al descargar",
        description: "No se pudo generar el archivo Excel",
        variant: "destructive",
      });
    }
  };

  const handleSendToEndpoint = async () => {
    try {
      const { data: response, error } = await supabase.functions.invoke(
        "send-to-endpoint",
        {
          body: { data },
        }
      );

      if (error) throw error;

      toast({
        title: "Enviado correctamente",
        description: `Respuesta: ${response.status} - ${response.message}`,
      });
    } catch (error) {
      toast({
        title: "Error al enviar",
        description: "No se pudo enviar los datos al endpoint",
        variant: "destructive",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Resultados</CardTitle>
          <div className="flex gap-2">
            <Button onClick={handleDownload} variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" />
              Descargar Excel
            </Button>
            <Button onClick={handleSendToEndpoint} size="sm">
              <Send className="mr-2 h-4 w-4" />
              Enviar a POSTMAN
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Total transacciones: <strong>{totalTransactions}</strong> | Suma de
          importes: <strong>{totalAmount.toLocaleString("es-PE", { minimumFractionDigits: 2 })}</strong>
        </p>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border max-h-[400px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>DNI/CEX</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Importe</TableHead>
                <TableHead>Referencia</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Código</TableHead>
                <TableHead>Descripción</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row, idx) => (
                <TableRow key={idx}>
                  <TableCell>{row["dni/cex"]}</TableCell>
                  <TableCell>{row.nombre}</TableCell>
                  <TableCell>{row.importe.toFixed(2)}</TableCell>
                  <TableCell>{row.Referencia}</TableCell>
                  <TableCell>{row.Estado}</TableCell>
                  <TableCell>{row["Codigo de Rechazo"]}</TableCell>
                  <TableCell>{row["Descripcion de Rechazo"]}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};

export default ResultsTable;
