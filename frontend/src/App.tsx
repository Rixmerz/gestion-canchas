import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { Layout } from "@/components/layout";
import { Agenda } from "@/routes/agenda";
import { Faltas } from "@/routes/faltas";
import { Gestion } from "@/routes/gestion";
import { Ingresar } from "@/routes/ingresar";
import { MisReservas } from "@/routes/mis-reservas";
import { Registro } from "@/routes/registro";
import { ProveedorDeSesion, useSesion } from "@/lib/sesion";

/** Ruta que exige sesión, y opcionalmente rol de administrador (M-03). */
function Protegida({
  children,
  soloAdministradores = false,
}: {
  children: React.ReactNode;
  soloAdministradores?: boolean;
}) {
  const { perfil, cargando } = useSesion();

  if (cargando) {
    return <p className="text-muted-foreground py-10 text-center text-sm">Cargando…</p>;
  }
  if (!perfil) return <Navigate to="/ingresar" replace />;
  if (soloAdministradores && !perfil.es_administrador) return <Navigate to="/" replace />;

  return <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <ProveedorDeSesion>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Agenda />} />
            <Route path="ingresar" element={<Ingresar />} />
            <Route path="registro" element={<Registro />} />
            <Route
              path="mis-reservas"
              element={
                <Protegida>
                  <MisReservas />
                </Protegida>
              }
            />
            <Route
              path="gestion"
              element={
                <Protegida soloAdministradores>
                  <Gestion />
                </Protegida>
              }
            />
            <Route
              path="faltas"
              element={
                <Protegida soloAdministradores>
                  <Faltas />
                </Protegida>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ProveedorDeSesion>
    </BrowserRouter>
  );
}
