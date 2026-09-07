import * as React from "react";

import { EstadoReservaBadge } from "@/components/estado";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { enFechaHora, enHora, enPesos } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import type { Reserva } from "@/lib/tipos";

/** M-17: el cliente ve el estado de sus solicitudes y su contador de faltas. */
export function MisReservas() {
  const { perfil } = useSesion();
  const [reservas, setReservas] = React.useState<Reserva[]>([]);
  const [cargando, setCargando] = React.useState(true);

  React.useEffect(() => {
    api.reservas()
      .then((pagina) => setReservas(pagina.results))
      .finally(() => setCargando(false));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Mis reservas</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Solicitar aparta el bloque; la reserva es real recién cuando pagas y el administrador
          confirma el pago. Si la ventana vence sin pago, el bloque se libera y se te registra una
          falta.
        </p>
      </header>

      {perfil && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Badge variant={perfil.bloqueado ? "vencida" : "outline"}>
              {perfil.faltas_vigentes} / {perfil.limite_faltas} faltas
            </Badge>
            <p className="text-muted-foreground text-sm">
              {perfil.bloqueado
                ? "Cuenta bloqueada: no puedes solicitar canchas."
                : `Te quedan ${perfil.faltas_restantes} antes del bloqueo automático.`}
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Historial</CardTitle>
          <CardDescription>Todas tus solicitudes, de la más nueva a la más antigua.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Cancha</TableHead>
                <TableHead>Bloque</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Vence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reservas.map((reserva) => (
                <TableRow key={reserva.id}>
                  <TableCell className="text-muted-foreground font-mono">{reserva.id}</TableCell>
                  <TableCell>{reserva.cancha.nombre}</TableCell>
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
                        <span>
                          {enHora(reserva.vence_en)}{" "}
                          <span className="text-warning">({reserva.minutos_para_vencer} min)</span>
                        </span>
                      )
                      : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                </TableRow>
              ))}
              {!cargando && reservas.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                    Todavía no has solicitado ninguna cancha.
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
