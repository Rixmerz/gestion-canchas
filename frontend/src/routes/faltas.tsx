import * as React from "react";
import { Unlock } from "lucide-react";

import { Aviso, type Nota } from "@/components/aviso";
import { Badge } from "@/components/ui/badge";
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
import { api } from "@/lib/api";
import { enFechaHora } from "@/lib/formato";
import type { Falta, ResumenFaltas } from "@/lib/tipos";

/** M-14 · M-15: quién no paga y quién ya quedó bloqueado. */
export function Faltas() {
  const [resumen, setResumen] = React.useState<ResumenFaltas | null>(null);
  const [detalle, setDetalle] = React.useState<Falta[]>([]);
  const [nota, setNota] = React.useState<Nota>(null);
  const [trabajando, setTrabajando] = React.useState<number | null>(null);

  const cargar = React.useCallback(async () => {
    const [nuevoResumen, pagina] = await Promise.all([api.resumenFaltas(), api.faltas()]);
    setResumen(nuevoResumen);
    setDetalle(pagina.results);
  }, []);

  React.useEffect(() => {
    cargar();
  }, [cargar]);

  async function desbloquear(id: number, nombre: string) {
    setTrabajando(id);
    setNota(null);
    try {
      await api.desbloquear(id);
      setNota({
        tipo: "exito",
        texto:
          `${nombre} quedó habilitado y sus faltas vigentes se anularon. Se conservan como ` +
          "historial: si no se anularan, el próximo barrido volvería a bloquearlo.",
      });
      await cargar();
    } catch (error) {
      setNota({ tipo: "error", texto: (error as Error).message });
    } finally {
      setTrabajando(null);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Vista de faltas</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Clientes que apartan bloques y no pagan dentro de la ventana (RN-04). Al llegar a{" "}
          <strong className="text-foreground">{resumen?.limite_faltas ?? 10} faltas vigentes</strong>
          {" "}el bloqueo es automático (RN-05).
        </p>
      </header>

      <Aviso nota={nota} />

      <Card>
        <CardHeader>
          <CardTitle>Clientes con faltas</CardTitle>
          <CardDescription>Ordenados de más a menos faltas vigentes.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cliente</TableHead>
                <TableHead>Correo</TableHead>
                <TableHead>Faltas</TableHead>
                <TableHead>Le quedan</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {resumen?.clientes.map((cliente) => (
                <TableRow key={cliente.id}>
                  <TableCell className="font-medium">{cliente.nombre}</TableCell>
                  <TableCell className="text-muted-foreground">{cliente.email || "—"}</TableCell>
                  <TableCell>
                    <strong>{cliente.total_faltas}</strong> / {resumen.limite_faltas}
                  </TableCell>
                  <TableCell>{cliente.faltas_restantes}</TableCell>
                  <TableCell>
                    {cliente.bloqueado
                      ? <Badge variant="vencida">BLOQUEADO</Badge>
                      : <Badge variant="outline">Habilitado</Badge>}
                  </TableCell>
                  <TableCell className="text-right">
                    {cliente.bloqueado && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={trabajando === cliente.id}
                        onClick={() => desbloquear(cliente.id, cliente.nombre)}
                      >
                        <Unlock /> Desbloquear
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {resumen?.clientes.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                    Ningún cliente tiene faltas vigentes.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Últimas faltas registradas</CardTitle>
          <CardDescription>Las registra el sistema al vencer una reserva impaga.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Reserva</TableHead>
                <TableHead>Cancha</TableHead>
                <TableHead>Motivo</TableHead>
                <TableHead>Registrada</TableHead>
                <TableHead>Vigente</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detalle.map((falta) => (
                <TableRow key={falta.id}>
                  <TableCell className="text-muted-foreground font-mono">{falta.id}</TableCell>
                  <TableCell>{falta.cliente.nombre}</TableCell>
                  <TableCell className="font-mono">#{falta.reserva}</TableCell>
                  <TableCell>{falta.cancha}</TableCell>
                  <TableCell className="whitespace-normal">{falta.motivo}</TableCell>
                  <TableCell>{enFechaHora(falta.registrada_en)}</TableCell>
                  <TableCell>{falta.vigente ? "Sí" : "Anulada"}</TableCell>
                </TableRow>
              ))}
              {detalle.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-muted-foreground py-6 text-center">
                    Sin faltas registradas.
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
