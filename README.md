# `eva2` — Producto Mínimo Viable (MVP) · persistencia en **SQLite3**

Rama del **MVP** del sistema de arrendamiento de canchas de fútbol. Aplicación **Django**
con base de datos **SQLite3**, autenticación, roles y Django Admin.

> **Alcance: solo los ítems _Must_ del MoSCoW** (M-01 … M-18).
> Ni un requisito Should, Could o Won't fue implementado.
>
> Documentación: [`docs/01-problema-y-solucion.md`](docs/01-problema-y-solucion.md) ·
> [`docs/02-moscow.md`](docs/02-moscow.md) · PoC en la rama [`eva1`](../../tree/eva1).

---

## Instalación

```bash
git clone https://github.com/Rixmerz/gestion-canchas.git
cd gestion-canchas
git checkout eva2

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py sembrar_demo      # canchas, usuarios y un escenario de prueba
python manage.py runserver
```

Aplicación: **http://127.0.0.1:8000/** · Administración: **http://127.0.0.1:8000/admin/**

### Cuentas que crea `sembrar_demo`

| Usuario | Clave | Perfil |
|---------|-------|--------|
| `admin` | `canchas2026` | Superusuario |
| `encargado` | `canchas2026` | **Administrador normal** (`is_staff`, rol `ADMIN`, sin ser superusuario) |
| `cmunoz`, `drojas`, `ivera`, `pcardenas` | `canchas2026` | Clientes |

Son credenciales de demostración para desarrollo local. Para un superusuario propio:
`python manage.py createsuperuser`.

### Pruebas

```bash
python manage.py test
```

39 pruebas, una por criterio de aceptación del MVP.

---

## Cómo se cubre cada ítem Must

| ID | Requisito | Dónde está |
|----|-----------|-----------|
| **M-01** | Modelo relacional en SQLite3 con migraciones | `reservas/models.py`, `reservas/migrations/` |
| **M-02** | Registro, login y logout | `reservas/forms.py`, `reservas/urls.py`, `/registro/`, `/ingresar/` |
| **M-03** | Roles `ADMIN` y `CLIENTE` con autorización por vista | `Usuario.rol`, `Usuario.es_administrador`, `views._solo_administradores` |
| **M-04** | Django Admin operativo | `reservas/admin.py` — canchas, reservas, faltas y usuarios |
| **M-05** | Administrador normal, no superusuario | `reservas/permisos.py` — grupo «Administradores de recinto», creado tras cada `migrate` |
| **M-06** | Catálogo de canchas | `Cancha` + `CanchaAdmin` |
| **M-07** | Agenda de disponibilidad | `servicios.bloques_del_dia`, `/` |
| **M-08** | Solicitud de reserva por el cliente | `servicios.solicitar_reserva`, `/solicitar/` |
| **M-09** | RN-01 · anticipación de 30 min | `reglas.validar_anticipacion` |
| **M-10** | RN-02 · ventana de pago | `reglas.calcular_vence_en` |
| **M-11** | RN-06 · sin solapamiento | `reglas.validar_sin_solapamiento` + `UniqueConstraint` en la base de datos |
| **M-12** | RN-03 · confirmación manual del pago | `servicios.confirmar_pago`, acción del `ReservaAdmin` |
| **M-13** | RN-04 · vencimiento y falta | `servicios.vencer_reservas_pendientes` |
| **M-14** | Vista de faltas | `/faltas/` + `FaltaAdmin` + contador en `UsuarioAdmin` |
| **M-15** | RN-05 · bloqueo a las 10 faltas | `servicios.evaluar_bloqueo`, `reglas.validar_cliente_habilitado` |
| **M-16** | RN-07 · zona horaria de Santiago | `settings.TIME_ZONE = "America/Santiago"`, `USE_TZ = True` |
| **M-17** | Mis reservas | `/mis-reservas/` |
| **M-18** | Vencimiento programable | `python manage.py vencer_reservas` + barrido perezoso |

---

## El ciclo de negocio

```
                 solicita (cliente, /solicitar/)
   [ no existe ] ────────────────────────────► [ PENDIENTE_PAGO ]
                                                       │
              admin confirma el pago en el Django Admin│  vence la ventana
        ┌──────────────────────────────────────────────┴────────────────────┐
        ▼                                                                   ▼
  [ PAGADA ]  reserva real                                     [ VENCIDA ]  + FALTA
        │                                                       libera el bloque
        │ admin cancela
        ▼
  [ CANCELADA ]  libera el bloque, sin falta
```

**Reglas aplicadas al solicitar**, en este orden y todas en el servidor:

1. La cancha está activa y quien solicita es un cliente, no un administrador.
2. **RN-05** — el cliente no está bloqueado ni llegó a 10 faltas vigentes.
3. **RN-01** — faltan al menos 30 minutos para el inicio del bloque.
4. **RN-06** — la cancha no tiene otra reserva vigente superpuesta.
5. **RN-02** — se calcula `vence_en = min(creada_en + 30 min, inicio)`.

Si alguna falla se lanza `reglas.ReglaViolada` y la transacción no deja rastro.

---

## Probarlo a mano en 5 minutos

1. Entrar como **`cmunoz`** y solicitar un bloque libre en la agenda → queda
   `PENDIENTE_PAGO` con su hora de vencimiento visible en **Mis reservas**.
2. Entrar en otra ventana como **`drojas`** e intentar el **mismo bloque** → lo rechaza
   **RN-06**.
3. Intentar un bloque que empieza en menos de 30 minutos → lo rechaza **RN-01**.
4. Entrar como **`encargado`** en `/admin/reservas/reserva/`, seleccionar la solicitud y
   aplicar la acción **«Confirmar pago»** → pasa a `PAGADA`, queda registrado quién y
   cuándo, y deja de vencer.
5. Dejar vencer otra solicitud sin pagarla y ejecutar `python manage.py vencer_reservas`
   (o simplemente recargar la agenda) → pasa a `VENCIDA`, el bloque se libera y aparece
   la falta.
6. En **Faltas** (`/faltas/`) está **`ivera`** con 9 faltas del escenario de prueba. Al
   solicitar y dejar vencer una más llega a 10 y queda **bloqueado** automáticamente: el
   sistema le rechaza toda nueva solicitud (**RN-05**).
7. Para habilitarlo: `/admin/reservas/usuario/` → seleccionar `ivera` → acción
   **«Desbloquear y anular sus faltas vigentes»**.

---

## Estructura

```
manage.py
config/settings.py           SQLite3, AUTH_USER_MODEL, TIME_ZONE America/Santiago
reservas/
  models.py                  Usuario · Cancha · Reserva · Falta  (M-01)
  reglas.py                  Python puro: RN-01, RN-02, RN-04, RN-05, RN-06, RN-07
  servicios.py               casos de uso sobre el ORM, en transacciones
  admin.py                   panel de gestión: confirmar pago, cancelar, faltas, bloqueos
  permisos.py                grupo del administrador normal (M-05)
  views.py  urls.py  forms.py
  templates/
  migrations/0001_initial.py
  management/commands/
    vencer_reservas.py       barrido de vencimientos (M-18), apto para cron
    sembrar_demo.py          escenario de demostración
  tests.py                   39 pruebas
```

`reglas.py` no importa Django: es el mismo núcleo validado en la PoC (rama `eva1`) y se
reutiliza aquí sin cambios sobre el modelo relacional.

---

## Decisiones de diseño

**Modelo de usuario propio desde el día uno.** `AUTH_USER_MODEL = "reservas.Usuario"`
extiende `AbstractUser` con `rol`, `telefono`, `bloqueado` y `bloqueado_en`. Cambiar el
modelo de usuario después de la primera migración es caro; hacerlo al inicio no cuesta nada.

**El bloqueo no es un campo que alguien edita a mano.** Lo escribe `evaluar_bloqueo()` al
cerrar el barrido de vencimientos. El administrador puede desbloquear, y esa acción anula
las faltas vigentes: si no lo hiciera, el siguiente barrido volvería a bloquear al cliente
—exactamente el problema que dejó al descubierto la PoC—. Las faltas anuladas quedan como
historial (`vigente=False`), no se borran.

**Doble barrera contra la sobreventa.** El servicio valida el solapamiento dentro de una
transacción, y la tabla tiene un `UniqueConstraint` condicional sobre
`(cancha, inicio)` para las reservas vigentes. Si dos solicitudes corren la misma carrera,
la base de datos decide y el `IntegrityError` se traduce a un mensaje de negocio.

**Una falta por reserva, garantizado por el esquema.** `Falta.reserva` es un
`OneToOneField`: repetir el barrido no puede duplicar una falta.

**Vencimiento sin broker de tareas.** El barrido corre de forma perezosa al abrir la
agenda o solicitar, y además está disponible como comando para cron. Meter Celery y Redis
en un MVP de un recinto sería sobre-ingeniería.

**Toda la hora en UTC, toda la presentación en Santiago.** `USE_TZ = True` con
`TIME_ZONE = "America/Santiago"`. Las sumas y comparaciones de fechas pasan por
`reglas.sumar`, `reglas.diferencia` y `reglas.en_utc`, que trabajan en UTC: sumar o restar
directamente sobre datetimes con zona opera el reloj de pared y se rompe en el cambio de
horario chileno.

---

## Lo que este MVP deliberadamente **no** hace

Pago en línea (C-01), notificaciones por correo (S-01), cancelación por el propio cliente
(S-02), caducidad automática de faltas (S-04), reportes de ocupación (S-05), bloques de
duración variable (S-06), reservas recurrentes (S-07), API REST (C-02) ni multi-sede
(C-03). Todo está clasificado y justificado en [`docs/02-moscow.md`](docs/02-moscow.md).
