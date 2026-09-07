# `eva3` — MVP desacoplado · **Django REST Framework** + **React (Deno)** + **shadcn/ui**

Migración de la rama [`eva2`](../../tree/eva2) a una arquitectura de dos piezas:
Django deja de renderizar HTML y expone una **API REST**; el front pasa a ser una **SPA
de React** servida por **Deno**, con componentes de **shadcn/ui** sobre Tailwind CSS v4.

> **El alcance no cambia: siguen siendo exactamente los 18 ítems _Must_ del MoSCoW.**
> Mismas reglas de negocio, misma base SQLite3, mismo Django Admin. Lo que cambia es cómo
> se entrega.
>
> Documentación: [`docs/01-problema-y-solucion.md`](docs/01-problema-y-solucion.md) ·
> [`docs/02-moscow.md`](docs/02-moscow.md) · PoC en [`eva1`](../../tree/eva1) ·
> MVP monolítico en [`eva2`](../../tree/eva2).

---

## Arquitectura

```
┌──────────────────────────────┐         ┌───────────────────────────────────────┐
│  SPA · React 19 + Deno       │  HTTP   │  Django 5.2 + Django REST Framework   │
│  Vite · Tailwind v4          │ ──────► │                                       │
│  shadcn/ui · react-router    │  JSON   │  api/        cáscara REST delgada     │
│  localhost:5173              │ ◄────── │  reservas/   dominio (sin cambios)    │
└──────────────────────────────┘  Token  │    reglas.py     RN-01 … RN-07        │
                                         │    servicios.py  casos de uso         │
                                         │    models.py     SQLite3              │
                                         │  /admin/     panel del recinto        │
                                         │  localhost:8000                       │
                                         └───────────────────────────────────────┘
```

**La regla que ordena todo:** `api/` no contiene lógica de negocio. Valida el formato de
entrada, llama a `reservas.servicios` y serializa el resultado. `reglas.py` y
`servicios.py` son **los mismos archivos de `eva2`**, sin una línea cambiada. Por eso la
migración no pudo introducir una segunda verdad sobre cuándo se puede reservar.

### Cómo viaja una regla infringida

En `eva2`, romper RN-01 era un mensaje en una plantilla. Aquí es un contrato HTTP:

```http
POST /api/reservas/   {"cancha": 3, "inicio": "2026-09-08T20:00:00-03:00"}

HTTP/1.1 409 Conflict
{
  "detail": "Solo se puede solicitar con al menos 30 minutos de anticipación: faltan 12 minutos.",
  "regla": "RN-01",
  "codigo": "regla_violada"
}
```

**409 Conflict**, no 400: la petición está bien formada; es el estado del negocio el que
la rechaza. El identificador de la regla viaja en el cuerpo, así que la SPA puede mostrar
*qué* regla se infringió, y otro cliente podría reaccionar distinto según cuál sea.

---

## Levantar el proyecto

Se necesitan **dos terminales**: la API y el front.

### 1 · API (Django + DRF)

```bash
git clone https://github.com/Rixmerz/gestion-canchas.git
cd gestion-canchas
git checkout eva3

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py sembrar_demo
python manage.py runserver          # http://127.0.0.1:8000
```

### 2 · Front (Deno + React)

```bash
cd frontend
deno task dev                       # http://localhost:5173
```

Deno instala las dependencias npm solo (`deno.json` + `deno.lock`); no hace falta Node ni
`npm install`. Vite proxea `/api` hacia `127.0.0.1:8000`, así que en desarrollo no hay
problemas de CORS ni URLs absolutas en el código.

| Dirección | Qué es |
|-----------|--------|
| http://localhost:5173 | La aplicación (SPA de React) |
| http://127.0.0.1:8000/api/ | API navegable de DRF |
| http://127.0.0.1:8000/admin/ | Django Admin — panel de gestión del recinto |

### Cuentas de `sembrar_demo`

| Usuario | Clave | Perfil |
|---------|-------|--------|
| `admin` | `canchas2026` | Superusuario |
| `encargado` | `canchas2026` | Administrador normal (`is_staff`, rol `ADMIN`, no superusuario) |
| `cmunoz`, `drojas`, `ivera`, `pcardenas` | `canchas2026` | Clientes |

Credenciales de demostración para desarrollo local.

### Pruebas

```bash
python manage.py test          # 68 pruebas: 36 de dominio + 32 de la API
cd frontend && deno task check # verificación de tipos de la SPA
cd frontend && deno task build # build de producción a frontend/dist/
```

---

## La API

Autenticación por **token** en la cabecera `Authorization: Token <clave>`. La sesión de
Django sigue habilitada para poder navegar la API desde el navegador con la misma cuenta
del admin.

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| `POST` | `/api/auth/registro/` | público | Crea un cliente y devuelve token + perfil (M-02) |
| `POST` | `/api/auth/login/` | público | Token + perfil |
| `POST` | `/api/auth/logout/` | sesión | Invalida el token |
| `GET` | `/api/auth/yo/` | sesión | Perfil, rol, faltas vigentes y estado de bloqueo |
| `GET` | `/api/canchas/` | público | Catálogo de canchas activas (M-06) |
| `GET` | `/api/agenda/?cancha=&fecha=` | público | Grilla del día en hora de Santiago (M-07) |
| `GET` | `/api/reservas/` | sesión | Mis reservas; todas si soy administrador (M-17, RN-08) |
| `POST` | `/api/reservas/` | cliente | **Solicitar un bloque** (M-08) |
| `POST` | `/api/reservas/{id}/confirmar-pago/` | admin | Convierte la solicitud en reserva real (M-12, RN-03) |
| `POST` | `/api/reservas/{id}/cancelar/` | admin | Libera el bloque, sin generar falta |
| `GET` | `/api/faltas/` | admin | Detalle de faltas registradas (M-14) |
| `GET` | `/api/faltas/resumen/` | admin | Clientes con faltas, de más a menos (M-14) |
| `POST` | `/api/clientes/{id}/desbloquear/` | admin | Habilita y anula sus faltas vigentes (M-15) |

Todos los endpoints de lectura corren antes el barrido de vencimientos (RN-04), así que
el estado que devuelve la API siempre está al día sin depender de un cron.

### Probar la API a mano

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"cmunoz","password":"canchas2026"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s "http://127.0.0.1:8000/api/agenda/?fecha=$(date -v+1d +%F)" | python3 -m json.tool | head -30

# Solicitar un bloque a menos de 30 minutos → 409 con la regla RN-01
curl -s -X POST http://127.0.0.1:8000/api/reservas/ \
  -H "Authorization: Token $TOKEN" -H 'Content-Type: application/json' \
  -d '{"cancha": 1, "inicio": "'"$(date -v+10M -u +%FT%TZ)"'"}'
```

---

## El front

```
frontend/
  deno.json               tareas y dependencias npm (sin package.json, sin node_modules a mano)
  deno.lock               instalación reproducible
  vite.config.ts          plugins de React y Tailwind v4 + proxy /api → :8000
  components.json         configuración de shadcn/ui (para agregar más componentes)
  src/
    index.css             tokens del sistema de diseño (Tailwind v4, configuración en CSS)
    App.tsx               rutas y guardas por rol
    lib/
      api.ts              cliente HTTP: tokens, errores, ErrorDeRegla
      tipos.ts            las formas que devuelve la API
      sesion.tsx          contexto de sesión, revalidado contra /auth/yo/
      formato.ts          fechas y pesos en convención chilena
      utils.ts            cn() de shadcn
    components/
      ui/                 shadcn/ui: button, card, badge, input, label, table, alert, select
      layout.tsx  estado.tsx  aviso.tsx
    routes/
      agenda.tsx  ingresar.tsx  registro.tsx
      mis-reservas.tsx  gestion.tsx  faltas.tsx
```

**shadcn/ui no es una dependencia**: sus componentes viven en `src/components/ui/` como
código propio, que es exactamente su premisa. `components.json` queda configurado por si
se quiere agregar más con `deno run -A npm:shadcn@latest add <componente>`.

**Deno sin Node.** Las dependencias npm se declaran en `deno.json` con especificadores
`npm:` y se instalan solas al correr la tarea. `deno task check` verifica tipos con el
TypeScript que trae Deno.

---

## Decisiones de la migración

**El dominio no se tocó.** `reservas/reglas.py`, `reservas/servicios.py` y
`reservas/models.py` son idénticos a `eva2`. Lo que desapareció fue la capa de
presentación de Django: `views.py`, `urls.py`, `forms.py` y las plantillas. Si la
migración hubiera exigido cambiar una regla, habría sido señal de que la regla estaba
enredada con la interfaz.

**El Django Admin se queda.** Es un ítem Must (M-04, M-05) y sigue siendo la herramienta
del encargado para todo lo que no es el día a día: crear canchas, corregir datos,
desbloquear clientes, revisar el historial. La SPA no lo reemplaza; le agrega el atajo
operativo de confirmar pagos sin entrar al admin.

**Token, no JWT.** Un token opaco de DRF alcanza para un recinto: no hay refresh, ni
rotación, ni claims que verificar sin tocar la base. JWT resolvería un problema que este
sistema no tiene.

**El servidor es el único reloj.** El front nunca calcula si faltan 30 minutos: pinta lo
que la API le dice (`disponible`, `a_tiempo`, `minutos_para_vencer`). El reloj del
navegador del cliente no puede abrir una reserva fuera de plazo.

**Paginación.** `PAGE_SIZE = 50` en DRF; las listas devuelven `{count, next, previous,
results}`. El cliente lee `.results`. Canchas va sin paginar: son cuatro.

---

## Lo que sigue sin hacer

Igual que en `eva2`: pago en línea (C-01), notificaciones (S-01), cancelación por el
cliente (S-02), caducidad de faltas (S-04), reportes (S-05), bloques de duración variable
(S-06), reservas recurrentes (S-07) y multi-sede (C-03).

Propios de esta arquitectura y también fuera de alcance: documentación OpenAPI/Swagger,
versionado de la API, refresh de tokens, service worker / modo offline, y despliegue del
front como estático detrás de la misma URL que la API.
