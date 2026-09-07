import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export type Nota = { tipo: "exito" | "error"; texto: string; regla?: string } | null;

/**
 * Un solo lugar para mostrar el resultado de una operación. Cuando el rechazo
 * viene de una regla de negocio, se muestra cuál: es la diferencia entre «no se
 * pudo» y «el sistema no lo permite, y esta es la razón».
 */
export function Aviso({ nota }: { nota: Nota }) {
  if (!nota) return null;

  if (nota.tipo === "exito") {
    return (
      <Alert variant="success" className="mb-6">
        <CheckCircle2 />
        <AlertTitle>Listo</AlertTitle>
        <AlertDescription>{nota.texto}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Alert variant="destructive" className="mb-6">
      {nota.regla ? <AlertTriangle /> : <Info />}
      <AlertTitle>
        {nota.regla ? `Regla de negocio ${nota.regla}` : "No se pudo completar"}
      </AlertTitle>
      <AlertDescription>{nota.texto}</AlertDescription>
    </Alert>
  );
}
