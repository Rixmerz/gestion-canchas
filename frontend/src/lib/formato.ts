/**
 * Presentación de fechas y montos en convención chilena.
 *
 * El backend entrega ISO-8601 con offset; aquí solo se formatea, nunca se hace
 * aritmética de fechas: los plazos los calcula el servidor, que es el único que
 * conoce la hora oficial del recinto.
 */

const ZONA = "America/Santiago";

const hora = new Intl.DateTimeFormat("es-CL", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: ZONA,
});

const fechaCorta = new Intl.DateTimeFormat("es-CL", {
  day: "2-digit",
  month: "2-digit",
  timeZone: ZONA,
});

const fechaHora = new Intl.DateTimeFormat("es-CL", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: ZONA,
});

const diaLargo = new Intl.DateTimeFormat("es-CL", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: ZONA,
});

const pesos = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

export const enHora = (iso: string) => hora.format(new Date(iso));
export const enFechaCorta = (iso: string) => fechaCorta.format(new Date(iso));
export const enFechaHora = (iso: string) => fechaHora.format(new Date(iso));
export const enDiaLargo = (iso: string) => diaLargo.format(new Date(iso));
export const enPesos = (monto: number) => pesos.format(monto);

/** Rango del bloque, como se lee en la cancha: «20:00 – 21:00». */
export const enRango = (inicio: string, fin: string) => `${enHora(inicio)} – ${enHora(fin)}`;

/** `YYYY-MM-DD` de hoy en hora de Santiago, para el selector de día. */
export function hoyEnSantiago(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA }).format(new Date());
}

/** Corre un `YYYY-MM-DD` en días, sin salir del calendario. */
export function correrDias(fecha: string, dias: number): string {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  const movido = new Date(Date.UTC(anio, mes - 1, dia + dias));
  return movido.toISOString().slice(0, 10);
}
