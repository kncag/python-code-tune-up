import { useState } from "react";
import CodeSelector from "./CodeSelector";
import FileUploader from "./FileUploader";
import ResultsTable from "./ResultsTable";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";

const PostBcpXlsx = () => {
  const [code, setCode] = useState("R001");
  const [desc, setDesc] = useState("DOCUMENTO ERRADO");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleCodeSelect = (newCode: string, newDesc: string) => {
    setCode(newCode);
    setDesc(newDesc);
  };

  const handleProcess = async () => {
    if (!pdfFile || !excelFile) {
      toast({
        title: "Archivos incompletos",
        description: "Debe seleccionar ambos archivos (PDF y Excel)",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("pdf", pdfFile);
      formData.append("excel", excelFile);
      formData.append("code", code);
      formData.append("desc", desc);

      const { data, error } = await supabase.functions.invoke(
        "process-post-bcp-xlsx",
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
        description: "No se pudieron procesar los archivos",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <CodeSelector selectedCode={code} onCodeSelect={handleCodeSelect} />

      <div className="grid grid-cols-2 gap-4">
        <FileUploader
          label="PDF de DNIs"
          accept=".pdf"
          file={pdfFile}
          onFileChange={setPdfFile}
          icon="pdf"
        />
        <FileUploader
          label="Excel masivo"
          accept=".xlsx,.xls"
          file={excelFile}
          onFileChange={setExcelFile}
          icon="excel"
        />
      </div>

      <Button
        onClick={handleProcess}
        disabled={!pdfFile || !excelFile || loading}
        className="w-full"
        size="lg"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Procesando...
          </>
        ) : (
          "Procesar archivos"
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

export default PostBcpXlsx;
