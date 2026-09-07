# Sistema de Gestión de Arrendamiento de Canchas de Fútbol

**Documento de definición del proyecto**
Versión 1.0 · Zona horaria de operación: `America/Santiago` (Santiago de Chile)

---

## 1. Contexto

El arriendo de canchas de fútbol (baby fútbol, futbolito, fútbol 7 y fútbol 11) es un
negocio de alta rotación: un recinto con 3 canchas y bloques de 60 minutos entre las
09:00 y las 23:00 mueve del orden de **42 bloques diarios**, es decir, más de **1.200
transacciones al mes**. Cada bloque es un inventario perecible: el bloque de las 20:00
que no se arrienda no se puede vender al día siguiente.

Hoy, la gran mayoría de estos recintos administra ese inventario **sin ningún sistema**:
un cuaderno en el mesón, una planilla Excel o —el caso más común— un grupo de WhatsApp
donde el encargado responde "¿está libre el jueves a las 21?".

---

## 2. Problemática de negocio

> **No existe una aplicación que permita gestionar el arrendamiento de canchas de fútbol:
> la disponibilidad, la reserva y el pago se administran de forma manual e informal, lo
> que produce sobreventa de bloques, pérdida de ingresos por reservas que nunca se pagan
> y cero trazabilidad sobre quién incumple.**

### 2.1 Dolores concretos

| # | Dolor | Descripción | Impacto |
|---|-------|-------------|---------|
| P1 | **Sin fuente única de disponibilidad** | El calendario vive en la cabeza o el cuaderno del encargado. El cliente no puede ver qué hay libre sin preguntar. | Fricción de venta; se pierden arriendos fuera del horario de atención. |
| P2 | **Doble reserva (sobreventa)** | Dos clientes reciben el mismo bloque por distintos canales (WhatsApp y mostrador). | Conflicto en cancha, devolución de dinero, daño reputacional. |
| P3 | **Reservas fantasma** | El cliente "aparta" el bloque y nunca paga ni avisa. El bloque queda ocupado y se pierde. | Pérdida directa de ingresos sobre inventario perecible. |
| P4 | **Sin registro de incumplimiento** | No hay memoria de quién ya falló antes; el mismo cliente vuelve a bloquear horarios. | Reincidencia sin costo, entorpecimiento del sistema. |
| P5 | **Estado de pago informal** | El pago se confirma "de palabra" o por captura de transferencia; nadie sabe qué está realmente pagado. | Descuadres de caja, discusiones en el mostrador. |
| P6 | **Cero información de gestión** | No hay datos de ocupación por bloque, cancha ni cliente. | Se fija precio y horario a ciegas. |
| P7 | **Errores de hora** | Confusiones de horario, agravadas por el cambio de horario de verano/invierno de Chile. | Clientes que llegan a la hora equivocada. |

### 2.2 Actores

- **Administrador del recinto** — publica canchas y bloques, confirma pagos, cancela,
  revisa faltas y bloquea clientes problemáticos.
- **Cliente** — se registra, inicia sesión, ve disponibilidad y solicita un bloque.
- **Sistema** — vence automáticamente las reservas no pagadas, registra faltas y bloquea
  al cliente al acumular el límite.

---

## 3. Solución propuesta

Una **aplicación web construida en Django** que centraliza el ciclo completo del arriendo
en un único origen de verdad, con dos perfiles de acceso y una máquina de estados
explícita para la reserva.

### 3.1 Idea central: *solicitar ≠ reservar*

El corazón de la solución es separar los dos actos que hoy se confunden:

```
  SOLICITUD (el cliente aparta)          RESERVA REAL (el negocio la reconoce)
  ─────────────────────────────          ────────────────────────────────────
  · La crea el cliente logueado          · La confirma el administrador
  · Bloquea el horario provisoriamente   · Bloquea el horario en firme
  · Tiene fecha de vencimiento           · No vence
  · Estado: PENDIENTE_PAGO               · Estado: PAGADA
```

Una solicitud es un **hold temporal**. Si el cliente paga y el administrador marca el pago
dentro de la ventana, el hold se convierte en reserva real. Si la ventana vence, el hold
muere, el bloque se libera automáticamente y **se registra una falta al cliente**.

### 3.2 Máquina de estados de la reserva

```
                 solicita (cliente)
   [ no existe ] ──────────────────► [ PENDIENTE_PAGO ]
                                            │
                    admin marca pagada      │      vence la ventana (sistema)
              ┌─────────────────────────────┴──────────────────────────┐
              ▼                                                        ▼
        [ PAGADA ]                                              [ VENCIDA ]
      reserva real, el                                    libera el bloque y
      bloque queda tomado                                 genera una FALTA
              │
              │ admin cancela
              ▼
       [ CANCELADA ]  ── libera el bloque, sin falta
```

### 3.3 Reglas de negocio

| ID | Regla | Detalle |
|----|-------|---------|
| **RN-01** | **Anticipación mínima de 30 minutos** | Un cliente solo puede solicitar un bloque si faltan **al menos 30 minutos** para su hora de inicio. A las 19:31 ya no se puede solicitar el bloque de las 20:00. |
| **RN-02** | **Ventana de pago de 30 minutos** | La solicitud vence en `min(creada_en + 30 min, inicio_del_bloque)`. El cliente siempre dispone de una ventana para pagar, y esa ventana nunca se extiende más allá del inicio del partido. |
| **RN-03** | **Confirmación manual del pago** | Solo un usuario administrador cambia el estado a `PAGADA`. El sistema no integra pasarela de pago en el MVP: el pago es presencial o por transferencia y el administrador lo valida. |
| **RN-04** | **Vencimiento automático y falta** | Al vencer la ventana sin pago, la reserva pasa a `VENCIDA`, el bloque se libera y se registra **una falta** al cliente, con la reserva de origen como evidencia. |
| **RN-05** | **Bloqueo a las 10 faltas** | Al acumular **10 faltas vigentes**, el cliente queda **bloqueado automáticamente** y el sistema rechaza toda nueva solicitud suya. El desbloqueo es una acción manual del administrador. |
| **RN-06** | **Sin solapamiento** | Una cancha no puede tener dos reservas en estado `PENDIENTE_PAGO` o `PAGADA` que se superpongan en el tiempo. |
| **RN-07** | **Horario de Santiago de Chile** | Todo instante se almacena en UTC y se presenta en `America/Santiago`. El cálculo de las ventanas de 30 minutos usa horario local con DST, de modo que el cambio de horario de verano no corre ni adelanta las reservas. |
| **RN-08** | **Solo el dueño ve lo suyo** | Un cliente ve y cancela únicamente sus propias reservas; el administrador ve todo. |

### 3.4 Perfiles de usuario

| Perfil | Acceso | Puede |
|--------|--------|-------|
| **Superusuario** (`is_superuser`) | Django Admin | Todo, incluida la gestión de usuarios y la configuración del recinto. |
| **Administrador** (`rol = ADMIN`, `is_staff`) | Django Admin + panel | Gestionar canchas, ver la agenda completa, **confirmar pagos**, cancelar reservas, ver el panel de faltas, bloquear y desbloquear clientes. |
| **Cliente** (`rol = CLIENTE`) | Aplicación web | Registrarse, iniciar sesión, ver disponibilidad, **solicitar** un bloque, ver sus reservas y su contador de faltas. |

### 3.5 Modelo de dominio

```
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│     Usuario      │        │      Cancha      │        │     Reserva      │
├──────────────────┤        ├──────────────────┤        ├──────────────────┤
│ username         │        │ nombre           │        │ cancha      (FK) │
│ email            │        │ tipo (7/11/baby) │◄───────│ cliente     (FK) │
│ rol              │◄───────│ superficie       │        │ inicio (aware)   │
│ bloqueado        │        │ precio_hora      │        │ fin    (aware)   │
│ faltas (deriv.)  │        │ activa           │        │ estado           │
└──────────────────┘        └──────────────────┘        │ creada_en        │
         ▲                                              │ vence_en         │
         │                                              │ pagada_en        │
         │              ┌──────────────────┐            │ confirmada_por   │
         └──────────────│      Falta       │────────────┘
                        ├──────────────────┤
                        │ cliente     (FK) │
                        │ reserva     (FK) │
                        │ motivo           │
                        │ registrada_en    │
                        │ vigente          │
                        └──────────────────┘
```

### 3.6 Alcance por rama del repositorio

| Rama | Entregable | Persistencia | Qué demuestra |
|------|-----------|--------------|---------------|
| `main` | Documentación | — | Problema, solución y MoSCoW. |
| `eva1` | **PoC** | Archivos **JSON** | Que las reglas de negocio críticas (RN-01, RN-02, RN-04, RN-05, RN-06, RN-07) son implementables y correctas, sin base de datos, sin ORM y sin migraciones. |
| `eva2` | **MVP** | **SQLite3** | El sistema completo con los ítems **Must** del MoSCoW: modelo relacional, autenticación, Django Admin, roles y el ciclo completo solicitud → pago → falta → bloqueo. |

---

## 4. Beneficios esperados

| Dolor | Cómo lo resuelve la solución |
|-------|------------------------------|
| P1 | Calendario de disponibilidad en línea, 24/7, con la hora oficial de Santiago. |
| P2 | Validación de solapamiento en el servidor (RN-06): el sistema rechaza el segundo intento. |
| P3 | Hold con vencimiento automático (RN-02, RN-04): el bloque no pagado vuelve al inventario solo. |
| P4 | Registro de faltas y bloqueo automático a las 10 (RN-05). |
| P5 | Estado explícito `PENDIENTE_PAGO` / `PAGADA`, con quién y cuándo confirmó el pago (RN-03). |
| P6 | Toda la operación queda en base de datos, consultable desde el Django Admin. |
| P7 | Almacenamiento en UTC y presentación en `America/Santiago` con DST (RN-07). |

---

## 5. Supuestos y decisiones

1. **El pago es fuera del sistema.** El MVP no integra Webpay/Transbank; el administrador
   confirma manualmente. La integración es un ítem *Could have*.
2. **La ventana de pago se interpreta como un hold de 30 minutos** acotado por el inicio
   del bloque (RN-02). Es la lectura que hace consistente el requisito "puede reservar con
   media hora de anticipación… si paga dentro de esa media".
3. **Un solo recinto.** Multi-sede queda fuera del MVP.
4. **Las faltas no prescriben** en el MVP; el campo `vigente` deja preparada la caducidad
   futura sin agregar complejidad hoy.
5. **El vencimiento se evalúa de forma perezosa** (al consultar la agenda o al solicitar) y
   además mediante el comando `manage.py vencer_reservas`, ejecutable por cron. No se
   introduce Celery ni un broker en el MVP.
6. **Bloques de duración fija de 60 minutos** en el MVP; la duración variable es *Should*.

---

## 6. Criterios de aceptación del MVP

- [ ] Un cliente no autenticado no puede solicitar ninguna cancha.
- [ ] Un cliente autenticado solicita un bloque libre y la reserva queda `PENDIENTE_PAGO`.
- [ ] El sistema rechaza una solicitud a menos de 30 minutos del inicio (RN-01).
- [ ] El sistema rechaza una solicitud que se solapa con otra vigente (RN-06).
- [ ] El administrador marca la reserva como `PAGADA` desde el Django Admin y esta deja de vencer.
- [ ] Una reserva no pagada dentro de la ventana pasa a `VENCIDA` y genera exactamente una falta.
- [ ] El panel de faltas lista a los clientes con reservas no pagadas, ordenados por cantidad.
- [ ] Un cliente que llega a 10 faltas queda bloqueado y no puede solicitar.
- [ ] Todas las horas se muestran en `America/Santiago`.
