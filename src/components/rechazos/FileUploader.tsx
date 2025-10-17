import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Upload, File } from "lucide-react";

interface FileUploaderProps {
  label: string;
  accept: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  icon?: "pdf" | "excel" | "txt" | "zip";
}

const FileUploader = ({
  label,
  accept,
  file,
  onFileChange,
  icon = "pdf",
}: FileUploaderProps) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    onFileChange(selectedFile);
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col items-center gap-4">
          <div className="text-center">
            <h4 className="font-medium mb-2">{label}</h4>
            {file ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <File className="h-4 w-4" />
                <span>{file.name}</span>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No se ha seleccionado archivo
              </p>
            )}
          </div>
          <Button onClick={handleClick} variant="outline" className="w-full">
            <Upload className="mr-2 h-4 w-4" />
            Seleccionar archivo
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleChange}
            className="hidden"
          />
        </div>
      </CardContent>
    </Card>
  );
};

export default FileUploader;
