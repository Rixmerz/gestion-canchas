# `eva1` — Prueba de Concepto (PoC) · persistencia en **JSON**

Rama de la **Prueba de Concepto** del sistema de arrendamiento de canchas de fútbol.
Aplicación **Django** que persiste todo en archivos **JSON** planos: sin base de datos,
sin ORM, sin migraciones y sin login.

> Documentación del proyecto (problema, solución, MoSCoW):
> [`docs/01-problema-y-solucion.md`](docs/01-problema-y-solucion.md) ·
> [`docs/02-moscow.md`](docs/02-moscow.md)
> El MVP completo está en la rama [`eva2`](../../tree/eva2).

---

## Qué pregunta responde esta PoC

> ¿Se pueden implementar correctamente las reglas críticas del arriendo —anticipación,
> ventana de pago, solapamiento, faltas y bloqueo— en horario de Santiago de Chile,
> **antes** de invertir en el modelo relacional, las migraciones y la autenticación?

**Respuesta: sí**, y en el intento aparecieron dos defectos de aritmética de fechas que
habrían llegado al MVP. Ver [Hallazgos](#hallazgos).

---

## Alcance

### Incluido

| Regla | Qué hace |
|-------|----------|
| **RN-01** | Solo se puede solicitar un bloque con **≥ 30 minutos** de anticipación. |
| **RN-02** | La solicitud vence en `min(creada_en + 30 min, inicio_del_bloque)`. |
| **RN-04** | Al vencer sin pago: `VENCIDA`, se libera el bloque y se registra **una falta**. |
| **RN-05** | A las **10 faltas** el cliente queda bloqueado y no puede solicitar. |
| **RN-06** | Una cancha no admite dos reservas vigentes superpuestas. |
| **RN-07** | Toda la aritmética ocurre en `America/Santiago`, con horario de verano. |

Pantallas: **Agenda** (disponibilidad y solicitud), **Gestión** (confirmar pago, cancelar)
y **Faltas** (quién no paga, quién está bloqueado).

### Excluido (entra recién en el MVP, rama `eva2`)

Base de datos SQLite3 y migraciones · autenticación y registro · roles con autorización
real · Django Admin · administrador no superusuario · trazabilidad de quién confirmó el
pago · pantalla "Mis reservas" · comando de vencimiento programado.

**En la PoC no hay login**: el cliente se elige en un selector y cualquiera puede entrar
a la pantalla de gestión. Es deliberado — la PoC prueba reglas, no seguridad.

---

## Instalación y ejecución

```bash
git clone https://github.com/Rixmerz/gestion-canchas.git
cd gestion-canchas
git checkout eva1

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py sembrar_demo      # carga un escenario de demostración
python manage.py runserver
```

Abrir **http://127.0.0.1:8000/**

No hay `migrate` ni `createsuperuser`: esta rama no tiene base de datos.

### Verificar las reglas de negocio

```bash
python -m unittest pruebas_reglas -v
```

25 pruebas sobre `canchas/reglas.py`, que es Python puro y no necesita Django ni servidor.

---

## Cómo probar el ciclo completo

1. **Agenda** → elegir cliente *Carlos Muñoz*, cancha y día → **Solicitar** un bloque libre.
   Queda `PENDIENTE_PAGO` con su hora de vencimiento a la vista.
2. Intentar solicitar **el mismo bloque** con otro cliente → lo rechaza **RN-06**.
3. Intentar solicitar un bloque que empieza **en menos de 30 minutos** → botón deshabilitado
   y, si se fuerza el POST, lo rechaza **RN-01**.
4. **Gestión** → *Marcar pagada* → la solicitud se convierte en **reserva real** (`PAGADA`)
   y deja de vencer.
5. Dejar pasar la ventana sin pagar → al recargar cualquier pantalla, la reserva pasa a
   `VENCIDA`, el bloque vuelve a estar libre y aparece una falta.
6. **Faltas** → *Ignacio Vera* llega con 9 faltas del escenario de demostración. Basta una
   más para que quede **BLOQUEADO** y el sistema le rechace toda solicitud (**RN-05**).

---

## Estructura

```
manage.py
pruebas_reglas.py            25 pruebas de las reglas de negocio
config/settings.py           DATABASES vacío; sesiones firmadas en cookie
canchas/
  reglas.py                  Python puro: RN-01, RN-02, RN-04, RN-05, RN-06, RN-07
  repositorio.py             lectura/escritura de los JSON (escritura atómica)
  servicios.py               casos de uso: solicitar, confirmar pago, vencer, faltas
  views.py  urls.py          agenda, gestión y faltas
  templates/canchas/
  management/commands/sembrar_demo.py
data/
  canchas.json               canchas del recinto y horario de operación
  clientes.json              clientes de prueba
  reservas.json              reservas, faltas y correlativos  ← se escribe en runtime
```

La separación `reglas` → `servicios` → `repositorio` es intencional: las reglas no saben
que existen los JSON, así que el MVP las reimplementa sobre el ORM sin tocar la lógica.

---

## Formato de los datos

`data/reservas.json`:

```json
{
  "secuencia": 12,
  "secuencia_faltas": 9,
  "reservas": [
    {
      "id": 12,
      "cancha_id": 3,
      "cliente_id": 1,
      "inicio": "2026-09-08T01:00:00-03:00",
      "fin": "2026-09-08T02:00:00-03:00",
      "estado": "PENDIENTE_PAGO",
      "creada_en": "2026-09-07T20:11:02-03:00",
      "vence_en": "2026-09-07T20:41:02-03:00",
      "pagada_en": null,
      "vencida_en": null,
      "precio": 28000
    }
  ],
  "faltas": [
    {
      "id": 1,
      "cliente_id": 3,
      "reserva_id": 3,
      "motivo": "No pagó dentro de la ventana de 30 minutos (RN-02).",
      "registrada_en": "2026-09-06T19:30:00-03:00"
    }
  ]
}
```

Todos los instantes van en ISO-8601 **con offset explícito**, en hora de Santiago.

---

## Hallazgos

La PoC cumplió su función: encontró dos bugs de fechas antes de que costaran caro.

1. **Sumar un `timedelta` a un datetime con zona hace aritmética de reloj de pared.**
   El 6 de septiembre de 2026 Chile adelanta el reloj y las 00:00 no existen; una ventana
   de pago que cruzaba ese instante quedaba mal calculada o apuntaba a una hora inexistente.
   Se resolvió con `reglas.sumar()`, que suma en UTC y vuelve a hora local.

2. **Restar o comparar dos datetimes que comparten `tzinfo` también ignora la zona.**
   Python compara los relojes de pared. Entre las 23:45 y las 01:00 de esa noche hay
   15 minutos reales, pero la resta directa devuelve 1 h 15 min: RN-01 habría aceptado
   solicitudes fuera de plazo. Se resolvió con `reglas.diferencia()` y `reglas.en_utc()`.

Ambos casos están cubiertos por las pruebas de la clase `AritmeticaDeTiempo`.

### Limitaciones que justifican pasar a SQLite3 en el MVP

- **Sin concurrencia.** Cada escritura reescribe el archivo completo; dos solicitudes
  simultáneas pueden pisarse. La validación de solapamiento no es atómica.
- **Sin integridad referencial.** Nada impide que una reserva apunte a una cancha borrada.
- **Consultas O(n) en memoria.** Contar faltas exige recorrer todo el archivo.
- **Sin autenticación.** Cualquiera puede actuar como cualquier cliente o como administrador.
- **El desbloqueo manual no dura**: como las faltas no tienen estado, el siguiente barrido
  vuelve a bloquear al cliente. El MVP lo corrige con faltas `vigentes`.
