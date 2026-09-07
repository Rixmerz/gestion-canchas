import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { CircleUser, LogOut, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSesion } from "@/lib/sesion";
import { cn } from "@/lib/utils";

function Enlace({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm transition-colors",
          isActive
            ? "bg-accent text-accent-foreground font-medium"
            : "text-muted-foreground hover:text-foreground",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function Layout() {
  const { perfil, salir } = useSesion();
  const navegar = useNavigate();

  async function cerrarSesion() {
    await salir();
    navegar("/");
  }

  return (
    <div className="min-h-dvh">
      <header className="border-border/70 bg-card/60 sticky top-0 z-20 border-b backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span aria-hidden>⚽</span>
            Arriendo de <span className="text-primary">Canchas</span>
          </Link>
          <Badge variant="outline" className="font-mono text-[10px] tracking-wider uppercase">
            eva3 · DRF + React
          </Badge>

          <nav className="ml-auto flex flex-wrap items-center gap-1">
            <Enlace to="/">Agenda</Enlace>
            {perfil && !perfil.es_administrador && <Enlace to="/mis-reservas">Mis reservas</Enlace>}
            {perfil?.es_administrador && (
              <>
                <Enlace to="/gestion">Gestión</Enlace>
                <Enlace to="/faltas">Faltas</Enlace>
                <a
                  href="http://127.0.0.1:8000/admin/"
                  target="_blank"
                  rel="noreferrer"
                  className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 text-sm"
                >
                  Django Admin
                </a>
              </>
            )}

            {perfil
              ? (
                <div className="ml-2 flex items-center gap-2">
                  <span className="text-muted-foreground flex items-center gap-1.5 text-sm">
                    <CircleUser className="size-4" />
                    {perfil.nombre}
                  </span>
                  {perfil.bloqueado && (
                    <Badge variant="vencida">
                      <ShieldAlert /> bloqueado
                    </Badge>
                  )}
                  <Button variant="ghost" size="sm" onClick={cerrarSesion}>
                    <LogOut /> Salir
                  </Button>
                </div>
              )
              : (
                <div className="ml-2 flex items-center gap-2">
                  <Button variant="ghost" size="sm" asChild>
                    <Link to="/ingresar">Ingresar</Link>
                  </Button>
                  <Button size="sm" asChild>
                    <Link to="/registro">Crear cuenta</Link>
                  </Button>
                </div>
              )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>

      <footer className="text-muted-foreground mx-auto max-w-6xl px-4 pb-10 text-xs leading-relaxed">
        SPA en React + Deno sobre una API de Django REST Framework · solo los ítems{" "}
        <strong className="text-foreground">Must</strong> del MoSCoW.
        <br />
        Zona horaria de operación: <strong className="text-foreground">America/Santiago</strong>
        {" "}· anticipación mínima 30 min (RN-01) · ventana de pago 30 min (RN-02) · bloqueo a las
        10 faltas (RN-05).
      </footer>
    </div>
  );
}
