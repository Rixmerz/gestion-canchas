import { Badge } from "@/components/ui/badge";
import type { EstadoReserva } from "@/lib/tipos";

const VARIANTES = {
  PENDIENTE_PAGO: "pendiente",
  PAGADA: "pagada",
  VENCIDA: "vencida",
  CANCELADA: "cancelada",
} as const;

const ETIQUETAS = {
  PENDIENTE_PAGO: "Pendiente de pago",
  PAGADA: "Pagada",
  VENCIDA: "Vencida",
  CANCELADA: "Cancelada",
} as const;

export function EstadoReservaBadge({ estado }: { estado: EstadoReserva }) {
  return <Badge variant={VARIANTES[estado]}>{ETIQUETAS[estado]}</Badge>;
}
