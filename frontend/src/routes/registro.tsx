import * as React from "react";
import { Link, useNavigate } from "react-router";

import { Aviso, type Nota } from "@/components/aviso";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorDeApi } from "@/lib/api";
import { useSesion } from "@/lib/sesion";

const CAMPOS = [
  { nombre: "username", etiqueta: "Nombre de usuario", tipo: "text", autoComplete: "username" },
  { nombre: "first_name", etiqueta: "Nombre", tipo: "text", autoComplete: "given-name" },
  { nombre: "last_name", etiqueta: "Apellido", tipo: "text", autoComplete: "family-name" },
  { nombre: "email", etiqueta: "Correo electrónico", tipo: "email", autoComplete: "email" },
  { nombre: "telefono", etiqueta: "Teléfono (opcional)", tipo: "tel", autoComplete: "tel" },
  { nombre: "password", etiqueta: "Contraseña", tipo: "password", autoComplete: "new-password" },
  {
    nombre: "password2",
    etiqueta: "Repetir contraseña",
    tipo: "password",
    autoComplete: "new-password",
  },
] as const;

/** M-02: alta de cliente. El backend fuerza el rol; aquí no hay forma de pedir ADMIN. */
export function Registro() {
  const { registrarse } = useSesion();
  const navegar = useNavigate();
  const [nota, setNota] = React.useState<Nota>(null);
  const [errores, setErrores] = React.useState<Record<string, string[]>>({});
  const [enviando, setEnviando] = React.useState(false);

  async function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget)) as Record<string, string>;
    setEnviando(true);
    setNota(null);
    setErrores({});
    try {
      await registrarse(datos);
      navegar("/");
    } catch (error) {
      if (error instanceof ErrorDeApi) setErrores(error.campos);
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
          <CardTitle className="text-xl">Crear cuenta de cliente</CardTitle>
          <CardDescription>
            Con tu cuenta puedes solicitar bloques y seguir el estado de tus reservas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={enviar} className="grid gap-4">
            {CAMPOS.map((campo) => (
              <div key={campo.nombre} className="grid gap-2">
                <Label htmlFor={campo.nombre}>{campo.etiqueta}</Label>
                <Input
                  id={campo.nombre}
                  name={campo.nombre}
                  type={campo.tipo}
                  autoComplete={campo.autoComplete}
                  required={campo.nombre !== "telefono"}
                  aria-invalid={Boolean(errores[campo.nombre])}
                />
                {errores[campo.nombre]?.map((mensaje) => (
                  <p key={mensaje} className="text-destructive text-xs">{mensaje}</p>
                ))}
              </div>
            ))}
            <Button type="submit" disabled={enviando}>
              {enviando ? "Creando…" : "Crear cuenta"}
            </Button>
          </form>

          <p className="text-muted-foreground mt-4 text-center text-sm">
            ¿Ya tienes cuenta?{" "}
            <Link to="/ingresar" className="text-primary underline-offset-4 hover:underline">
              Ingresar
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
