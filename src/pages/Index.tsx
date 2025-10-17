import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileText, Upload } from "lucide-react";
import PreBcpTxt from "@/components/rechazos/PreBcpTxt";
import PreBcpXlsx from "@/components/rechazos/PreBcpXlsx";
import RechazoIbk from "@/components/rechazos/RechazoIbk";
import PostBcpXlsx from "@/components/rechazos/PostBcpXlsx";

const Index = () => {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-secondary/20">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <FileText className="h-10 w-10 text-primary" />
            <h1 className="text-4xl font-bold">Rechazos Masivos</h1>
          </div>
          <p className="text-muted-foreground text-lg">
            Sistema unificado de procesamiento de rechazos bancarios
          </p>
        </div>

        <Tabs defaultValue="pre-txt" className="w-full">
          <TabsList className="grid w-full grid-cols-4 mb-8">
            <TabsTrigger value="pre-txt">PRE BCP-txt</TabsTrigger>
            <TabsTrigger value="pre-xlsx">PRE BCP-xlsx</TabsTrigger>
            <TabsTrigger value="ibk">Rechazo IBK</TabsTrigger>
            <TabsTrigger value="post-xlsx">POST BCP-xlsx</TabsTrigger>
          </TabsList>

          <TabsContent value="pre-txt">
            <PreBcpTxt />
          </TabsContent>

          <TabsContent value="pre-xlsx">
            <PreBcpXlsx />
          </TabsContent>

          <TabsContent value="ibk">
            <RechazoIbk />
          </TabsContent>

          <TabsContent value="post-xlsx">
            <PostBcpXlsx />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default Index;
