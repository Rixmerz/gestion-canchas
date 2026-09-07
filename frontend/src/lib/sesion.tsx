/**
 * Sesión del usuario.
 *
 * El token vive en `localStorage` y el perfil se revalida contra
 * `/api/auth/yo/` al arrancar: así el contador de faltas y el estado de bloqueo
 * que ve la SPA siempre vienen del servidor, nunca de una copia local que se
 * pudo quedar atrás.
 */

import * as React from "react";

import { api, borrarToken, guardarToken, leerToken } from "@/lib/api";
import type { Perfil } from "@/lib/tipos";

interface Sesion {
  perfil: Perfil | null;
  cargando: boolean;
  ingresar: (usuario: string, clave: string) => Promise<void>;
  registrarse: (datos: Record<string, string>) => Promise<void>;
  salir: () => Promise<void>;
  refrescar: () => Promise<void>;
}

const Contexto = React.createContext<Sesion | null>(null);

export function ProveedorDeSesion({ children }: { children: React.ReactNode }) {
  const [perfil, setPerfil] = React.useState<Perfil | null>(null);
  const [cargando, setCargando] = React.useState(true);

  const refrescar = React.useCallback(async () => {
    if (!leerToken()) {
      setPerfil(null);
      return;
    }
    try {
      setPerfil(await api.yo());
    } catch {
      borrarToken();
      setPerfil(null);
    }
  }, []);

  React.useEffect(() => {
    refrescar().finally(() => setCargando(false));
  }, [refrescar]);

  const valor: Sesion = {
    perfil,
    cargando,
    refrescar,
    async ingresar(usuario, clave) {
      const sesion = await api.login(usuario, clave);
      guardarToken(sesion.token);
      setPerfil(sesion.perfil);
    },
    async registrarse(datos) {
      const sesion = await api.registro(datos);
      guardarToken(sesion.token);
      setPerfil(sesion.perfil);
    },
    async salir() {
      try {
        await api.logout();
      } finally {
        borrarToken();
        setPerfil(null);
      }
    },
  };

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSesion(): Sesion {
  const sesion = React.useContext(Contexto);
  if (!sesion) throw new Error("useSesion debe usarse dentro de <ProveedorDeSesion>.");
  return sesion;
}
