import * as React from "react";
import { BadgeCheck, Ban } from "lucide-react";

import { Aviso, type Nota } from "@/components/aviso";
import { EstadoReservaBadge } from "@/components/estado";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ErrorDeRegla } from "@/lib/api";
import { enFechaHora, enHora, enPesos } from "@/lib/formato";
import type { Reserva } from "@/lib/tipos";

/**
 * M-12 · RN-03: la solicitud se convierte en reserva real solo cuando un
 * administrador confirma el pago. El Django Admin sigue disponible para lo
 * demás; esto es el atajo operativo del día a día.
 */
export function Gestion() {
  const [reservas, setReservas] = React.useState<Reserva[]>([]);
  const [nota, setNota] = React.useState<Nota>(null);
  const [trabajando, setTrabajando] = React.useState<number | null>(null);

  const cargar = React.useCallback(async () => {
    const pagina = await api.reservas();
    setReservas(pagina.results);
  }, []);

  React.useEffect(() => {
    cargar();
  }, [cargar]);

  async function accionar(id: number, accion: "pagar" | "cancelar") {
    setTrabajando(id);
    setNota(null);
    try {
      const reserva = accion === "pagar" ? await api.confirmarPago(id) : await api.cancelar(id);
      setNota({
        tipo: "exito",
        texto: accion === "pagar"
          ? `Reserva #${reserva.id} marcada como PAGADA: el bloque queda tomado en firme.`
          : `Reserva #${reserva.id} cancelada; el bloque volvió a estar libre.`,
      });
      await cargar();
    } catch (error) {
      setNota(
        error instanceof ErrorDeRegla
          ? { tipo: "error", texto: error.message, regla: error.regla }
          : { tipo: "error", texto: (error as Error).message },
      );
      await cargar();
    } finally {
      setTrabajando(null);
    }
  }

  const pendientes = reservas.filter((r) => r.estado === "PENDIENTE_PAGO");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Gestión de reservas</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Hay {pendientes.length} solicitud(es) esperando pago. Confirmar el pago es lo que
          convierte la solicitud en reserva real (RN-03).
        </p>
      </header>

      <Aviso nota={nota} />

      <Card>
        <CardHeader>
          <CardTitle>Todas las reservas</CardTitle>
          <CardDescription>De la más nueva a la más antigua.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Cancha</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Bloque</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Vence</TableHead>
                <TableHead>Confirmó</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reservas.map((reserva) => (
                <TableRow key={reserva.id}>
                  <TableCell className="text-muted-foreground font-mono">{reserva.id}</TableCell>
                  <TableCell>{reserva.cancha.nombre}</TableCell>
                  <TableCell>{reserva.cliente.nombre}</TableCell>
                  <TableCell>
                    {enFechaHora(reserva.inicio)} – {enHora(reserva.fin)}
                  </TableCell>
                  <TableCell>{enPesos(reserva.precio)}</TableCell>
                  <TableCell>
                    <EstadoReservaBadge estado={reserva.estado} />
                  </TableCell>
                  <TableCell>
                    {reserva.estado === "PENDIENTE_PAGO"
                      ? (
                        <span className="text-warning">
                          {enHora(reserva.vence_en)} ({reserva.minutos_para_vencer} min)
                        </span>
                      )
                      : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {reserva.confirmada_por?.nombre ?? "—"}
                  </TableCell>
                  <TableCell className="space-x-2 text-right">
                    {reserva.estado === "PENDIENTE_PAGO" && (
                      <Button
                        size="sm"
                        disabled={trabajando === reserva.id}
                        onClick={() => accionar(reserva.id, "pagar")}
                      >
                        <BadgeCheck /> Marcar pagada
                      </Button>
                    )}
                    {reserva.es_vigente && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={trabajando === reserva.id}
                        onClick={() => accionar(reserva.id, "cancelar")}
                      >
                        <Ban /> Cancelar
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {reservas.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-muted-foreground py-6 text-center">
                    Todavía no hay reservas.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
