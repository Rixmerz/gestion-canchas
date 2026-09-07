/**
 * Cliente HTTP de la API.
 *
 * Un solo lugar que sabe de tokens, cabeceras y errores. Cuando la respuesta
 * es un 409 con `regla`, el error que se propaga es una `ErrorDeRegla`: la
 * interfaz puede distinguir "el negocio dice que no" de "algo se rompió".
 */

import type {
  Agenda,
  Cancha,
  Falta,
  Pagina,
  Perfil,
  Reserva,
  ResumenFaltas,
  Sesion,
} from "@/lib/tipos";

const BASE = "/api";
const LLAVE_TOKEN = "canchas.token";

export function leerToken(): string | null {
  return localStorage.getItem(LLAVE_TOKEN);
}

export function guardarToken(token: string) {
  localStorage.setItem(LLAVE_TOKEN, token);
}

export function borrarToken() {
  localStorage.removeItem(LLAVE_TOKEN);
}

/** Una regla de negocio rechazó la operación (HTTP 409). */
export class ErrorDeRegla extends Error {
  constructor(mensaje: string, readonly regla: string) {
    super(mensaje);
    this.name = "ErrorDeRegla";
  }
}

/** Cualquier otro error de la API, con el código HTTP y el detalle por campo. */
export class ErrorDeApi extends Error {
  constructor(
    mensaje: string,
    readonly estado: number,
    readonly campos: Record<string, string[]> = {},
  ) {
    super(mensaje);
    this.name = "ErrorDeApi";
  }
}

function mensajeDe(cuerpo: unknown, estado: number): string {
  if (cuerpo && typeof cuerpo === "object") {
    const datos = cuerpo as Record<string, unknown>;
    if (typeof datos.detail === "string") return datos.detail;
    const primero = Object.values(datos).find(Array.isArray) as string[] | undefined;
    if (primero?.length) return String(primero[0]);
  }
  return `Error ${estado} al hablar con el servidor.`;
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = leerToken();
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...opciones.headers,
    },
  });

  if (respuesta.status === 204) return undefined as T;

  const cuerpo = await respuesta.json().catch(() => null);

  if (!respuesta.ok) {
    if (respuesta.status === 409 && cuerpo?.regla) {
      throw new ErrorDeRegla(mensajeDe(cuerpo, 409), cuerpo.regla);
    }
    if (respuesta.status === 401) borrarToken();
    const campos: Record<string, string[]> = {};
    if (cuerpo && typeof cuerpo === "object") {
      for (const [clave, valor] of Object.entries(cuerpo)) {
        if (Array.isArray(valor)) campos[clave] = valor.map(String);
      }
    }
    throw new ErrorDeApi(mensajeDe(cuerpo, respuesta.status), respuesta.status, campos);
  }

  return cuerpo as T;
}

const enviar = <T>(ruta: string, datos?: unknown) =>
  pedir<T>(ruta, { method: "POST", body: datos ? JSON.stringify(datos) : undefined });

export const api = {
  // Autenticación (M-02)
  login: (username: string, password: string) =>
    enviar<Sesion>("/auth/login/", { username, password }),
  registro: (datos: Record<string, string>) => enviar<Sesion>("/auth/registro/", datos),
  logout: () => enviar<void>("/auth/logout/"),
  yo: () => pedir<Perfil>("/auth/yo/"),

  // Catálogo y agenda (M-06, M-07)
  canchas: () => pedir<Cancha[]>("/canchas/"),
  agenda: (cancha: number | null, fecha: string) =>
    pedir<Agenda>(`/agenda/?fecha=${fecha}${cancha ? `&cancha=${cancha}` : ""}`),

  // Reservas (M-08, M-12, M-17)
  reservas: (estado?: string) =>
    pedir<Pagina<Reserva>>(`/reservas/${estado ? `?estado=${estado}` : ""}`),
  solicitar: (cancha: number, inicio: string) =>
    enviar<Reserva>("/reservas/", { cancha, inicio }),
  confirmarPago: (id: number) => enviar<Reserva>(`/reservas/${id}/confirmar-pago/`),
  cancelar: (id: number) => enviar<Reserva>(`/reservas/${id}/cancelar/`),

  // Faltas (M-14, M-15)
  resumenFaltas: () => pedir<ResumenFaltas>("/faltas/resumen/"),
  faltas: () => pedir<Pagina<Falta>>("/faltas/"),
  desbloquear: (clienteId: number) => enviar<Perfil>(`/clientes/${clienteId}/desbloquear/`),
};
