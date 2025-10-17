import { useState } from "react";
import FileUploader from "./FileUploader";
import ResultsTable from "./ResultsTable";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";

const RechazoIbk = () => {
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleProcess = async () => {
    if (!zipFile) {
      toast({
        title: "Archivo faltante",
        description: "Debe seleccionar el archivo ZIP",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("zip", zipFile);

      const { data, error } = await supabase.functions.invoke(
        "process-rechazo-ibk",
        {
          body: formData,
        }
      );

      if (error) throw error;

      setResults(data);
      toast({
        title: "Procesamiento exitoso",
        description: `Se procesaron ${data.results.length} registros`,
      });
    } catch (error) {
      toast({
        title: "Error al procesar",
        description: "No se pudo procesar el archivo ZIP",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <FileUploader
        label="Archivo ZIP con Excel"
        accept=".zip"
        file={zipFile}
        onFileChange={setZipFile}
        icon="zip"
      />

      <Button
        onClick={handleProcess}
        disabled={!zipFile || loading}
        className="w-full"
        size="lg"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Procesando...
          </>
        ) : (
          "Procesar archivo ZIP"
        )}
      </Button>

      {results && (
        <ResultsTable
          data={results.results}
          totalTransactions={results.totalTransactions}
          totalAmount={results.totalAmount}
        />
      )}
    </div>
  );
};

export default RechazoIbk;
