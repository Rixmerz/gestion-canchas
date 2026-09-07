import * as React from "react";
import { Link } from "react-router";
import { CalendarDays, ChevronLeft, ChevronRight, Clock, Lock } from "lucide-react";

import { Aviso, type Nota } from "@/components/aviso";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ErrorDeRegla } from "@/lib/api";
import { correrDias, enDiaLargo, enFechaHora, enHora, enPesos, hoyEnSantiago } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import type { Agenda as AgendaDTO, Bloque, Cancha } from "@/lib/tipos";
import { cn } from "@/lib/utils";

/** M-07: disponibilidad por cancha y día. Pública: mirar no exige cuenta. */
export function Agenda() {
  const { perfil, refrescar } = useSesion();
  const [canchas, setCanchas] = React.useState<Cancha[]>([]);
  const [canchaId, setCanchaId] = React.useState<number | null>(null);
  const [fecha, setFecha] = React.useState(hoyEnSantiago());
  const [agenda, setAgenda] = React.useState<AgendaDTO | null>(null);
  const [nota, setNota] = React.useState<Nota>(null);
  const [enviando, setEnviando] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.canchas().then((lista) => {
      setCanchas(lista);
      setCanchaId((actual) => actual ?? lista[0]?.id ?? null);
    }).catch(() => setNota({ tipo: "error", texto: "No se pudo cargar el catálogo de canchas." }));
  }, []);

  const cargarAgenda = React.useCallback(async () => {
    try {
      setAgenda(await api.agenda(canchaId, fecha));
    } catch {
      setAgenda(null);
    }
  }, [canchaId, fecha]);

  React.useEffect(() => {
    cargarAgenda();
  }, [cargarAgenda]);

  async function solicitar(bloque: Bloque) {
    if (!canchaId) return;
    setEnviando(bloque.inicio);
    setNota(null);
    try {
      const reserva = await api.solicitar(canchaId, bloque.inicio);
      setNota({
        tipo: "exito",
        texto:
          `Solicitud #${reserva.id} creada para el ${enFechaHora(reserva.inicio)}. Queda ` +
          `pendiente de pago hasta las ${enHora(reserva.vence_en)}: paga y pide al ` +
          `administrador que confirme, o se libera el bloque y se te registra una falta.`,
      });
      await Promise.all([cargarAgenda(), refrescar()]);
    } catch (error) {
      setNota(
        error instanceof ErrorDeRegla
          ? { tipo: "error", texto: error.message, regla: error.regla }
          : { tipo: "error", texto: (error as Error).message },
      );
      await cargarAgenda();
    } finally {
      setEnviando(null);
    }
  }

  const cancha = agenda?.cancha ?? canchas.find((c) => c.id === canchaId);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Disponibilidad</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {agenda && (
            <>
              Hora oficial del recinto:{" "}
              <strong className="text-foreground">{enFechaHora(agenda.ahora)}</strong>{" "}
              ({agenda.zona_horaria}). Solo se puede solicitar un bloque con al menos{" "}
              {agenda.anticipacion_minima_min} minutos de anticipación.
            </>
          )}
        </p>
      </header>

      <Aviso nota={nota} />

      {perfil && !perfil.es_administrador && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Badge variant={perfil.bloqueado ? "vencida" : "outline"}>
              {perfil.faltas_vigentes} / {perfil.limite_faltas} faltas
            </Badge>
            <p className="text-muted-foreground text-sm">
              {perfil.bloqueado
                ? `Acumulaste ${perfil.limite_faltas} faltas por reservas no pagadas: no puedes solicitar canchas hasta que el administrador te habilite.`
                : `Te quedan ${perfil.faltas_restantes} faltas antes del bloqueo automático.`}
            </p>
          </CardContent>
        </Card>
      )}

      {!perfil && (
        <Card>
          <CardContent className="text-sm">
            Puedes mirar la disponibilidad sin cuenta, pero para solicitar una cancha necesitas
            {" "}
            <Link to="/ingresar" className="text-primary underline-offset-4 hover:underline">
              ingresar
            </Link>{" "}
            o{" "}
            <Link to="/registro" className="text-primary underline-offset-4 hover:underline">
              crear una cuenta
            </Link>.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="cancha">Cancha</Label>
            <Select
              value={canchaId ? String(canchaId) : undefined}
              onValueChange={(valor) => setCanchaId(Number(valor))}
            >
              <SelectTrigger id="cancha" className="w-[280px]">
                <SelectValue placeholder="Elegir cancha" />
              </SelectTrigger>
              <SelectContent>
                {canchas.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nombre} — {enPesos(c.precio_hora)}/hora
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="fecha">Día</Label>
            <Input
              id="fecha"
              type="date"
              className="w-[170px]"
              value={fecha}
              onChange={(evento) => setFecha(evento.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setFecha(correrDias(fecha, -1))}>
              <ChevronLeft /> Día anterior
            </Button>
            <Button variant="outline" onClick={() => setFecha(correrDias(fecha, 1))}>
              Día siguiente <ChevronRight />
            </Button>
            <Button variant="ghost" onClick={() => setFecha(hoyEnSantiago())}>
              <CalendarDays /> Hoy
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {cancha?.nombre ?? "Cancha"} · {agenda ? enDiaLargo(`${agenda.fecha}T12:00:00`) : ""}
          </CardTitle>
          <CardDescription>
            {cancha
              ? `${cancha.tipo_display} · ${cancha.superficie} · ${enPesos(cancha.precio_hora)} por hora`
              : "Cargando…"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-3">
            {agenda?.bloques.map((bloque) => (
              <BloqueCard
                key={bloque.inicio}
                bloque={bloque}
                autenticado={Boolean(perfil)}
                esCliente={Boolean(perfil && !perfil.es_administrador)}
                bloqueado={Boolean(perfil?.bloqueado)}
                enviando={enviando === bloque.inicio}
                onSolicitar={() => solicitar(bloque)}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function BloqueCard({
  bloque,
  autenticado,
  esCliente,
  bloqueado,
  enviando,
  onSolicitar,
}: {
  bloque: Bloque;
  autenticado: boolean;
  esCliente: boolean;
  bloqueado: boolean;
  enviando: boolean;
  onSolicitar: () => void;
}) {
  const ocupado = bloque.estado === "PAGADA" || bloque.estado === "PENDIENTE_PAGO";

  return (
    <div
      className={cn(
        "bg-secondary/40 rounded-lg border p-3 transition-colors",
        bloque.disponible && "border-primary/40 bg-primary/5",
        ocupado && "opacity-75",
      )}
    >
      <div className="font-mono text-base font-semibold tracking-tight">
        {enHora(bloque.inicio)} – {enHora(bloque.fin)}
      </div>

      <div className="mt-2 mb-3 min-h-7 text-xs">
        {bloque.estado === "PAGADA" && <Badge variant="pagada">Reservada</Badge>}
        {bloque.estado === "PENDIENTE_PAGO" && (
          <Badge variant="pendiente">Apartada, sin pagar</Badge>
        )}
        {bloque.estado === "FUERA_DE_PLAZO" && (
          <span className="text-muted-foreground flex items-center gap-1">
            <Clock className="size-3" /> Fuera de plazo (RN-01)
          </span>
        )}
        {bloque.estado === "LIBRE" && <span className="text-muted-foreground">Libre</span>}
      </div>

      {esCliente
        ? (
          <Button
            size="sm"
            className="w-full"
            /* Un bloque que no se puede pedir no debe verse como un botón vivo. */
            variant={bloque.disponible && !bloqueado ? "default" : "outline"}
            disabled={!bloque.disponible || bloqueado || enviando}
            onClick={onSolicitar}
          >
            {bloqueado
              ? <><Lock /> Bloqueado</>
              : ocupado
              ? "No disponible"
              : !bloque.a_tiempo
              ? "Muy tarde"
              : enviando
              ? "Solicitando…"
              : "Solicitar"}
          </Button>
        )
        : !autenticado && bloque.disponible
        ? (
          <Button size="sm" variant="outline" className="w-full" asChild>
            <Link to="/ingresar">Ingresar para solicitar</Link>
          </Button>
        )
        : (
          <Button size="sm" variant="outline" className="w-full" disabled>
            {ocupado ? "No disponible" : !bloque.a_tiempo ? "Muy tarde" : "Solo clientes"}
          </Button>
        )}
    </div>
  );
}
