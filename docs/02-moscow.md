# Priorización MoSCoW

Sistema de Gestión de Arrendamiento de Canchas de Fútbol · Versión 1.0

La técnica MoSCoW clasifica los requisitos en cuatro categorías —**M**ust have,
**S**hould have, **C**ould have, **W**on't have— para fijar qué entra en cada entrega y,
sobre todo, qué **no** entra.

**Regla de corte aplicada:** la rama `eva2` (MVP) implementa **exclusivamente los ítems
Must (M)**. Ni un ítem Should, Could o Won't fue implementado en el MVP.
La rama `eva1` (PoC) implementa un subconjunto aún menor —solo las reglas de negocio
críticas sobre archivos JSON— para probar la viabilidad antes de construir el MVP.

---

## MUST HAVE — imprescindible (MVP, rama `eva2`, SQLite3)

Sin esto el sistema no resuelve la problemática y no es entregable.

| ID | Requisito | Justificación |
|----|-----------|---------------|
| **M-01** | Modelo de datos relacional en **SQLite3**: `Usuario`, `Cancha`, `Reserva`, `Falta`, con migraciones Django. | Origen único de verdad; sin esto no hay sistema (P1). |
| **M-02** | **Autenticación**: registro de cliente, login y logout. | Toda solicitud debe ser atribuible a una persona (P4). |
| **M-03** | **Dos roles**: `ADMIN` y `CLIENTE`, con autorización efectiva por vista. | Separa quién solicita de quién confirma el pago (RN-03, RN-08). |
| **M-04** | **Django Admin operativo** para el superusuario y el administrador: ABM de canchas, reservas, usuarios y faltas. | Es el panel de gestión del MVP; evita construir un back-office propio. |
| **M-05** | **Usuario administrador normal** (`is_staff`, rol `ADMIN`) capaz de gestionar el arrendamiento completo sin ser superusuario. | El encargado del recinto no debe tener permisos de superusuario. |
| **M-06** | **Catálogo de canchas** con tipo, superficie, precio por hora y estado activa/inactiva. | Es el inventario que se arrienda. |
| **M-07** | **Agenda de disponibilidad** por cancha y día, en hora de Santiago. | Resuelve P1: el cliente ve qué hay libre sin preguntar. |
| **M-08** | **Solicitud de reserva** por el cliente autenticado; queda en estado `PENDIENTE_PAGO`. | Es el acto central: solicitar ≠ reservar. |
| **M-09** | **RN-01 · Anticipación mínima de 30 minutos** respecto del inicio del bloque. | Requisito explícito del negocio. |
| **M-10** | **RN-02 · Ventana de pago** `vence_en = min(creada_en + 30 min, inicio)`. | Define cuándo el hold muere. |
| **M-11** | **RN-06 · Validación de solapamiento** por cancha, en el servidor. | Resuelve P2 (sobreventa). |
| **M-12** | **RN-03 · Confirmación manual del pago** por el administrador → estado `PAGADA` (reserva real), con registro de quién y cuándo. | Resuelve P5. |
| **M-13** | **RN-04 · Vencimiento automático** de la reserva no pagada → `VENCIDA`, liberación del bloque y registro de **una** falta. | Resuelve P3 (reservas fantasma). |
| **M-14** | **Vista de faltas**: listado de clientes con reservas no pagadas y su conteo, accesible al administrador. | Requisito explícito: saber quién entorpece el sistema (P4). |
| **M-15** | **RN-05 · Bloqueo automático a las 10 faltas** y rechazo de toda solicitud del cliente bloqueado. | Requisito explícito del negocio. |
| **M-16** | **RN-07 · Zona horaria `America/Santiago`** con `USE_TZ=True`: almacenamiento en UTC, presentación y cálculo en hora local con DST. | Resuelve P7; condiciona toda la aritmética de las reglas. |
| **M-17** | **"Mis reservas"**: el cliente ve el estado y el vencimiento de sus solicitudes y su contador de faltas. | Sin esto el cliente no sabe que debe pagar ni por qué lo bloquearon. |
| **M-18** | **Comando `manage.py vencer_reservas`** + evaluación perezosa del vencimiento. | Hace que RN-04 ocurra sin intervención humana ni broker de tareas. |

---

## SHOULD HAVE — importante, pero no bloquea la entrega

Aporta valor real; se posterga a la siguiente iteración porque el MVP funciona sin ello.

| ID | Requisito | Por qué no es Must |
|----|-----------|--------------------|
| **S-01** | Notificación por correo al solicitar, al confirmar el pago y al vencer. | El cliente ya ve el estado en "Mis reservas" (M-17). |
| **S-02** | Cancelación de la solicitud por el propio cliente antes del vencimiento. | Sin ella el hold simplemente vence solo; nadie queda bloqueado. |
| **S-03** | Desbloqueo con motivo y bitácora de auditoría. | El administrador ya puede desbloquear desde el Django Admin (M-04). |
| **S-04** | Caducidad de faltas (p. ej. las mayores a 6 meses dejan de contar). | El campo `vigente` ya lo deja preparado; la política aún no está definida. |
| **S-05** | Reportes de ocupación por cancha, día y horario. | Es información de gestión (P6), no operación crítica. |
| **S-06** | Bloques de duración variable (30, 60, 90, 120 minutos). | El MVP opera con bloques fijos de 60 minutos. |
| **S-07** | Reservas recurrentes ("todos los jueves a las 21:00"). | Alto valor comercial, alta complejidad de calendario. |
| **S-08** | Calendario visual semanal en vez de listado por día. | Es una mejora de presentación sobre M-07. |
| **S-09** | Tarifas diferenciadas por horario (punta / valle) y por día. | El precio por hora fijo (M-06) basta para operar. |

---

## COULD HAVE — deseable si sobra tiempo

Mejora la experiencia, pero su ausencia no afecta la operación.

| ID | Requisito |
|----|-----------|
| **C-01** | Integración de pago en línea (Webpay Plus / Transbank / Mercado Pago) con confirmación automática, reemplazando la confirmación manual RN-03. |
| **C-02** | API REST (Django REST Framework) para consumo desde otras aplicaciones. |
| **C-03** | Multi-sede: varios recintos con sus propias canchas y administradores. |
| **C-04** | Lista de espera: avisar al cliente cuando se libera un bloque vencido. |
| **C-05** | Valoraciones y comentarios de los clientes sobre la cancha. |
| **C-06** | Arriendo de implementos adicionales (petos, balones, arbitraje, iluminación). |
| **C-07** | Exportación de reservas y faltas a CSV/Excel. |
| **C-08** | Panel de indicadores: tasa de no-pago, ocupación mensual, ingresos proyectados. |
| **C-09** | Autenticación social (Google) para acelerar el registro. |

---

## WON'T HAVE (this time) — fuera de alcance, explícitamente

Se descartan de forma consciente para esta versión. Se documentan para que nadie los
asuma incluidos.

| ID | Requisito | Motivo del descarte |
|----|-----------|---------------------|
| **W-01** | Aplicación móvil nativa (iOS/Android). | La web responsiva cubre el caso de uso; duplica el costo de desarrollo. |
| **W-02** | Emisión de boleta/factura electrónica e integración con el SII. | Requiere certificación tributaria; excede la gestión de arriendo. |
| **W-03** | Gestión de torneos, ligas, fixtures y tablas de posiciones. | Es un producto distinto, no el arriendo de bloques. |
| **W-04** | Chat en vivo entre cliente y administrador. | WhatsApp ya cubre esa necesidad hoy. |
| **W-05** | Predicción de demanda o precios dinámicos con machine learning. | No hay volumen de datos histórico que lo sustente. |
| **W-06** | Streaming o grabación de partidos. | Ajeno a la problemática de negocio planteada. |
| **W-07** | Nómina, control de asistencia y RR.HH. del recinto. | Otro dominio de negocio. |
| **W-08** | Reembolsos y devoluciones automáticas de dinero. | Sin pasarela de pago (C-01) no hay dinero que devolver dentro del sistema. |

---

## Alcance de la Prueba de Concepto — rama `eva1` (JSON)

La PoC **no** implementa el MVP. Su único objetivo es **demostrar que las reglas de negocio
críticas se pueden implementar correctamente** antes de invertir en el modelo relacional,
las migraciones y la autenticación.

**Persistencia:** archivos **JSON** planos en `data/` (`canchas.json`, `reservas.json`,
`clientes.json`). Sin base de datos, sin ORM, sin migraciones.

| De MoSCoW | En la PoC |
|-----------|-----------|
| M-06 | Catálogo de canchas leído desde `data/canchas.json`. |
| M-07 | Agenda de disponibilidad calculada sobre los bloques del JSON. |
| M-08 | Solicitud de reserva escrita en `data/reservas.json`. |
| M-09 (RN-01) | Validación de anticipación mínima de 30 minutos. |
| M-10 (RN-02) | Cálculo de `vence_en`. |
| M-11 (RN-06) | Validación de solapamiento. |
| M-13 (RN-04) | Vencimiento y registro de falta. |
| M-15 (RN-05) | Conteo de faltas y bloqueo a las 10. |
| M-16 (RN-07) | Toda la aritmética en `America/Santiago`. |

**Excluido de la PoC** (entra recién en el MVP): base de datos SQLite3 y migraciones
(M-01), autenticación real y registro (M-02), roles con autorización (M-03), Django Admin
(M-04, M-05), administrador no superusuario (M-05), confirmación de pago con trazabilidad
de quién y cuándo (M-12), vista de faltas para el administrador (M-14), "Mis reservas"
(M-17) y el comando de vencimiento (M-18). En la PoC el cliente se elige desde un selector
—no hay login— y el "administrador" es cualquiera que use la pantalla de gestión.

---

## Resumen de trazabilidad

| Categoría | Ítems | Rama que los implementa |
|-----------|-------|-------------------------|
| Must | 18 (M-01 … M-18) | `eva2` — MVP con SQLite3 · `eva3` — el mismo alcance sobre DRF + React |
| Should | 9 (S-01 … S-09) | No implementados |
| Could | 9 (C-01 … C-09) | No implementados |
| Won't | 8 (W-01 … W-08) | Fuera de alcance |
| Subconjunto PoC | 9 reglas críticas | `eva1` — PoC con JSON |

**Nota sobre `eva3`.** La migración a Django REST Framework + React **no cambia el
alcance**: implementa exactamente los mismos 18 ítems Must, con las mismas reglas y la
misma base de datos. Es un cambio de arquitectura de entrega, no de producto. En
particular, **C-02 (API REST para consumo de terceros) sigue siendo un Could**: `eva3`
expone la API porque su propio front la necesita, no como producto para integradores —
no hay versionado, ni contrato público, ni documentación OpenAPI, ni claves de terceros.
