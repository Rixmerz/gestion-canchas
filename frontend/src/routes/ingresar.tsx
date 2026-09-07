import * as React from "react";
import { Link, useNavigate } from "react-router";

import { Aviso, type Nota } from "@/components/aviso";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSesion } from "@/lib/sesion";

/** M-02: ingreso. Clientes y administradores usan la misma pantalla. */
export function Ingresar() {
  const { ingresar } = useSesion();
  const navegar = useNavigate();
  const [nota, setNota] = React.useState<Nota>(null);
  const [enviando, setEnviando] = React.useState(false);

  async function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    setEnviando(true);
    setNota(null);
    try {
      await ingresar(String(datos.get("username")), String(datos.get("password")));
      navegar("/");
    } catch (error) {
      setNota({ tipo: "error", texto: (error as Error).message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Aviso nota={nota} />
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Ingresar</CardTitle>
          <CardDescription>
            Los administradores del recinto ingresan con la misma cuenta.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={enviar} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="username">Nombre de usuario</Label>
              <Input id="username" name="username" autoComplete="username" required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" disabled={enviando}>
              {enviando ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>

          <p className="text-muted-foreground mt-4 text-center text-sm">
            ¿No tienes cuenta?{" "}
            <Link to="/registro" className="text-primary underline-offset-4 hover:underline">
              Crear una
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
