import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface CodeSelectorProps {
  selectedCode: string;
  onCodeSelect: (code: string, desc: string) => void;
}

const CODE_OPTIONS = {
  R001: "DOCUMENTO ERRADO",
  R002: "CUENTA INVALIDA",
  R007: "RECHAZO POR CCI",
};

const CodeSelector = ({ selectedCode, onCodeSelect }: CodeSelectorProps) => {
  return (
    <Card className="mb-6">
      <CardContent className="pt-6">
        <h3 className="text-lg font-semibold mb-4 text-center">
          Seleccionar código de rechazo
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(CODE_OPTIONS).map(([code, desc]) => (
            <Button
              key={code}
              variant={selectedCode === code ? "default" : "outline"}
              onClick={() => onCodeSelect(code, desc)}
              className="h-auto py-4 flex flex-col items-center gap-2"
            >
              <span className="font-bold">{code}</span>
              <span className="text-xs text-center whitespace-normal">
                {desc}
              </span>
            </Button>
          ))}
        </div>
        {selectedCode && (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Código seleccionado:{" "}
            <strong>
              {selectedCode} – {CODE_OPTIONS[selectedCode as keyof typeof CODE_OPTIONS]}
            </strong>
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export default CodeSelector;
