/** Formas que devuelve la API de Django REST Framework. */

export type EstadoReserva = "PENDIENTE_PAGO" | "PAGADA" | "VENCIDA" | "CANCELADA";
export type EstadoBloque = EstadoReserva | "LIBRE" | "FUERA_DE_PLAZO";

export interface Cancha {
  id: number;
  nombre: string;
  tipo: string;
  tipo_display: string;
  superficie: string;
  precio_hora: number;
  activa: boolean;
}

export interface Perfil {
  id: number;
  username: string;
  nombre: string;
  first_name: string;
  last_name: string;
  email: string;
  telefono: string;
  rol: "ADMIN" | "CLIENTE";
  es_administrador: boolean;
  bloqueado: boolean;
  bloqueado_en: string | null;
  faltas_vigentes: number;
  faltas_restantes: number;
  limite_faltas: number;
}

export interface UsuarioResumen {
  id: number;
  username: string;
  nombre: string;
}

export interface Reserva {
  id: number;
  cancha: Cancha;
  cliente: UsuarioResumen;
  inicio: string;
  fin: string;
  estado: EstadoReserva;
  estado_display: string;
  es_vigente: boolean;
  precio: number;
  creada_en: string;
  vence_en: string;
  minutos_para_vencer: number | null;
  pagada_en: string | null;
  vencida_en: string | null;
  confirmada_por: UsuarioResumen | null;
}

export interface Bloque {
  inicio: string;
  fin: string;
  disponible: boolean;
  a_tiempo: boolean;
  estado: EstadoBloque;
  reserva_id: number | null;
}

export interface Agenda {
  cancha: Cancha;
  fecha: string;
  ahora: string;
  zona_horaria: string;
  anticipacion_minima_min: number;
  bloques: Bloque[];
}

export interface Falta {
  id: number;
  cliente: UsuarioResumen;
  reserva: number;
  cancha: string;
  motivo: string;
  registrada_en: string;
  vigente: boolean;
}

export interface ClienteConFaltas {
  id: number;
  username: string;
  nombre: string;
  email: string;
  total_faltas: number;
  faltas_restantes: number;
  bloqueado: boolean;
}

export interface ResumenFaltas {
  limite_faltas: number;
  clientes: ClienteConFaltas[];
}

export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Sesion {
  token: string;
  perfil: Perfil;
}
