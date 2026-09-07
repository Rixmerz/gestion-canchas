# Gestión de Arrendamiento de Canchas de Fútbol

Sistema web en **Django** para administrar el arriendo de canchas de fútbol: catálogo de
canchas, disponibilidad, solicitud de reserva por el cliente, confirmación manual del pago
por el administrador, registro de faltas y bloqueo automático del cliente incumplidor.

Zona horaria de operación: **`America/Santiago`** (Santiago de Chile).

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`docs/01-problema-y-solucion.md`](docs/01-problema-y-solucion.md) | Problemática de negocio, solución propuesta, máquina de estados, reglas de negocio (RN-01 … RN-08), modelo de dominio y criterios de aceptación. |
| [`docs/02-moscow.md`](docs/02-moscow.md) | Priorización MoSCoW completa (18 Must, 9 Should, 9 Could, 8 Won't) y el alcance de la PoC y del MVP. |

---

## Estructura del repositorio por ramas

| Rama | Entregable | Stack | Alcance |
|------|-----------|-------|---------|
| **`main`** | Documentación | — | Problema, solución y MoSCoW. Sin código de aplicación. |
| **`eva1`** | **PoC** | Django · archivos **JSON** | Prueba de viabilidad de las reglas de negocio críticas. Sin base de datos, sin ORM, sin migraciones, sin login. |
| **`eva2`** | **MVP** | Django · **SQLite3** | Solo los ítems **Must (M-01 … M-18)** del MoSCoW: modelo relacional, autenticación, roles, Django Admin, ciclo completo solicitud → pago → falta → bloqueo. |
| **`eva3`** | **MVP desacoplado** | **Django REST Framework** + **React (Deno)** + **shadcn/ui** · SQLite3 | El mismo alcance de `eva2`, migrado a API REST y SPA. Mismo dominio, mismas reglas, misma base de datos. |

```bash
git checkout eva1   # Prueba de Concepto (JSON)
git checkout eva2   # Producto Mínimo Viable (SQLite3)
git checkout eva3   # MVP desacoplado (DRF + React/Deno)
```

Cada rama trae su propio `README.md` con las instrucciones de instalación y ejecución.

---

## Idea central del sistema

> **Solicitar no es reservar.**

El cliente **solicita** un bloque y este queda apartado con vencimiento
(`PENDIENTE_PAGO`). La **reserva real** existe recién cuando el cliente paga y el
administrador confirma el pago manualmente (`PAGADA`). Si la ventana de pago vence, el
bloque se libera solo y se registra una **falta** al cliente. A las **10 faltas** el
cliente queda **bloqueado** automáticamente.

```
                 solicita (cliente)
   [ no existe ] ──────────────────► [ PENDIENTE_PAGO ]
                                            │
                    admin marca pagada      │      vence la ventana (sistema)
              ┌─────────────────────────────┴──────────────────────────┐
              ▼                                                        ▼
        [ PAGADA ]                                              [ VENCIDA ]
      reserva real                                        libera el bloque + FALTA
```

Reglas clave: anticipación mínima de **30 minutos** (RN-01), ventana de pago de
**30 minutos** acotada al inicio del bloque (RN-02), sin solapamiento por cancha (RN-06)
y toda la aritmética en hora de Santiago con horario de verano (RN-07).

---

## Stack

| Capa | `eva1` | `eva2` | `eva3` |
|------|--------|--------|--------|
| Lenguaje | Python 3.13 | Python 3.13 | Python 3.13 · TypeScript |
| Backend | Django 5.2 | Django 5.2 | Django 5.2 + Django REST Framework |
| Persistencia | Archivos JSON | SQLite3 | SQLite3 |
| Front | Plantillas de Django | Plantillas de Django | React 19 sobre **Deno** (Vite) con **shadcn/ui** y Tailwind v4 |
| Panel de gestión | Pantalla propia | Django Admin | Django Admin + pantalla propia en la SPA |
| Pruebas | 25 (reglas puras) | 39 | 68 (36 de dominio + 32 de la API) |
