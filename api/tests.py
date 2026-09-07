"""
Pruebas de la capa REST.

Verifican el contrato de la API: códigos de estado, forma de la respuesta,
autenticación por token y —sobre todo— que las reglas de negocio sigan
aplicándose igual que en la rama `eva2`, ahora traducidas a HTTP 409 con el
identificador de la regla que falló.

    python manage.py test api
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from reservas import reglas, servicios
from reservas.models import Cancha, Falta, Reserva, Usuario
from reservas.permisos import NOMBRE_GRUPO

CLAVE = "clave-de-prueba-3821"


class BaseAPI(APITestCase):
    def setUp(self):
        self.cancha = Cancha.objects.create(
            nombre="Cancha 1", tipo=Cancha.Tipo.FUTBOL_7, precio_hora=40000
        )
        self.cliente = Usuario.objects.create_user(
            username="cmunoz", password=CLAVE, first_name="Carlos", last_name="Muñoz"
        )
        self.otro_cliente = Usuario.objects.create_user(
            username="drojas", password=CLAVE, first_name="Daniela", last_name="Rojas"
        )
        self.encargado = Usuario.objects.create_user(
            username="encargado", password=CLAVE, rol=Usuario.Rol.ADMIN, is_staff=True
        )
        self.encargado.groups.add(Group.objects.get(name=NOMBRE_GRUPO))

    def autenticar(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token

    def bloque(self, horas=3):
        """
        Un bloque en punto, **al menos** `horas` más adelante. Se redondea hacia
        arriba: truncar puede dejarlo a menos de 30 minutos y RN-01 lo
        rechazaría según la hora a la que se corran las pruebas.
        """
        momento = timezone.localtime(timezone.now()) + timedelta(hours=horas)
        en_punto = momento.replace(minute=0, second=0, microsecond=0)
        return en_punto if en_punto == momento else reglas.sumar(en_punto, timedelta(hours=1))

    def solicitar(self, horas=3, cancha=None):
        return self.client.post(
            "/api/reservas/",
            {"cancha": (cancha or self.cancha).pk, "inicio": self.bloque(horas).isoformat()},
            format="json",
        )


class Autenticacion(BaseAPI):
    """M-02 sobre REST: registro, login, logout y perfil."""

    def test_el_registro_devuelve_token_y_perfil(self):
        respuesta = self.client.post(
            "/api/auth/registro/",
            {
                "username": "nuevo",
                "first_name": "Ana",
                "last_name": "Soto",
                "email": "ana@example.cl",
                "password": "UnaClaveLarga2026",
                "password2": "UnaClaveLarga2026",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", respuesta.data)
        self.assertEqual(respuesta.data["perfil"]["rol"], Usuario.Rol.CLIENTE)
        self.assertFalse(respuesta.data["perfil"]["es_administrador"])

    def test_el_registro_no_permite_crear_administradores(self):
        self.client.post(
            "/api/auth/registro/",
            {
                "username": "colado",
                "first_name": "Colado",
                "last_name": "Falso",
                "email": "colado@example.cl",
                "rol": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
                "password": "UnaClaveLarga2026",
                "password2": "UnaClaveLarga2026",
            },
            format="json",
        )
        colado = Usuario.objects.get(username="colado")
        self.assertEqual(colado.rol, Usuario.Rol.CLIENTE)
        self.assertFalse(colado.is_staff)
        self.assertFalse(colado.is_superuser)

    def test_el_registro_rechaza_contrasenas_distintas(self):
        respuesta = self.client.post(
            "/api/auth/registro/",
            {
                "username": "nuevo",
                "first_name": "Ana",
                "last_name": "Soto",
                "email": "ana@example.cl",
                "password": "UnaClaveLarga2026",
                "password2": "OtraClaveLarga2026",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password2", respuesta.data)

    def test_login_correcto(self):
        respuesta = self.client.post(
            "/api/auth/login/", {"username": "cmunoz", "password": CLAVE}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["perfil"]["username"], "cmunoz")
        self.assertEqual(respuesta.data["perfil"]["limite_faltas"], reglas.FALTAS_PARA_BLOQUEO)

    def test_login_incorrecto_devuelve_401(self):
        respuesta = self.client.post(
            "/api/auth/login/", {"username": "cmunoz", "password": "no-es"}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(respuesta.data["codigo"], "credenciales")

    def test_yo_exige_token(self):
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, 401)
        self.autenticar(self.cliente)
        respuesta = self.client.get("/api/auth/yo/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["nombre"], "Carlos Muñoz")
        self.assertEqual(respuesta.data["faltas_restantes"], reglas.FALTAS_PARA_BLOQUEO)

    def test_logout_invalida_el_token(self):
        self.autenticar(self.cliente)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, 401)


class CatalogoYAgenda(BaseAPI):
    """M-06 y M-07: se pueden consultar sin cuenta."""

    def test_las_canchas_son_publicas(self):
        respuesta = self.client.get("/api/canchas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 1)

    def test_no_lista_canchas_inactivas(self):
        Cancha.objects.create(nombre="En mantención", precio_hora=1000, activa=False)
        self.assertEqual(len(self.client.get("/api/canchas/").data), 1)

    def test_la_agenda_es_publica_y_trae_catorce_bloques(self):
        respuesta = self.client.get("/api/agenda/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data["bloques"]), 14)
        self.assertEqual(respuesta.data["zona_horaria"], "America/Santiago")
        self.assertEqual(respuesta.data["anticipacion_minima_min"], 30)

    def test_marca_el_bloque_tomado(self):
        self.autenticar(self.cliente)
        inicio = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
        self.client.post(
            "/api/reservas/", {"cancha": self.cancha.pk, "inicio": inicio.isoformat()}, format="json"
        )
        self.client.credentials()
        respuesta = self.client.get(
            f"/api/agenda/?cancha={self.cancha.pk}&fecha={inicio.date().isoformat()}"
        )
        bloque = next(b for b in respuesta.data["bloques"] if b["estado"] == "PENDIENTE_PAGO")
        self.assertFalse(bloque["disponible"])
        self.assertIsNotNone(bloque["reserva_id"])


class SolicitarPorAPI(BaseAPI):
    """M-08: el caso de uso central, ahora como POST /api/reservas/."""

    def test_un_anonimo_no_puede_solicitar(self):
        self.assertEqual(self.solicitar().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_el_cliente_autenticado_crea_una_solicitud_pendiente(self):
        self.autenticar(self.cliente)
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data["estado"], "PENDIENTE_PAGO")
        self.assertEqual(respuesta.data["cancha"]["nombre"], "Cancha 1")
        self.assertEqual(respuesta.data["cliente"]["nombre"], "Carlos Muñoz")
        self.assertIsNotNone(respuesta.data["vence_en"])

    def test_una_cancha_inexistente_es_400(self):
        self.autenticar(self.cliente)
        respuesta = self.client.post(
            "/api/reservas/", {"cancha": 9999, "inicio": self.bloque().isoformat()}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_administrador_no_solicita_canchas(self):
        self.autenticar(self.encargado)
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["regla"], "RN-08")


class ReglasTraducidasAHttp(BaseAPI):
    """
    Las reglas de negocio no cambian al pasar a REST: siguen siendo las mismas
    y viajan como 409 con el identificador de la regla que se infringió.
    """

    def test_rn01_anticipacion_minima(self):
        self.autenticar(self.cliente)
        respuesta = self.client.post(
            "/api/reservas/",
            {
                "cancha": self.cancha.pk,
                "inicio": (timezone.now() + timedelta(minutes=20)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["regla"], "RN-01")
        self.assertEqual(respuesta.data["codigo"], "regla_violada")
        self.assertEqual(Reserva.objects.count(), 0)

    def test_rn02_ventana_de_pago_en_la_respuesta(self):
        self.autenticar(self.cliente)
        datos = self.solicitar(horas=5).data
        reserva = Reserva.objects.get(pk=datos["id"])
        self.assertEqual(
            reglas.diferencia(reserva.vence_en, reserva.creada_en), reglas.VENTANA_DE_PAGO
        )
        self.assertIsNotNone(datos["minutos_para_vencer"])

    def test_rn06_sin_solapamiento(self):
        self.autenticar(self.cliente)
        self.solicitar()
        self.autenticar(self.otro_cliente)
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["regla"], "RN-06")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_rn05_cliente_bloqueado(self):
        for numero in range(10):
            momento = timezone.now() - timedelta(days=numero + 1)
            reserva = Reserva.objects.create(
                cancha=self.cancha,
                cliente=self.cliente,
                inicio=momento,
                fin=momento + timedelta(hours=1),
                estado=Reserva.Estado.VENCIDA,
                precio=1000,
                vence_en=momento,
            )
            Falta.objects.create(cliente=self.cliente, reserva=reserva, motivo="prueba")
        servicios.evaluar_bloqueo(self.cliente)

        self.autenticar(self.cliente)
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["regla"], "RN-05")
        self.assertTrue(self.client.get("/api/auth/yo/").data["bloqueado"])


class ConfirmarPagoPorAPI(BaseAPI):
    """M-12 · RN-03."""

    def crear_pendiente(self):
        self.autenticar(self.cliente)
        return self.solicitar().data["id"]

    def test_el_administrador_confirma_el_pago(self):
        reserva_id = self.crear_pendiente()
        self.autenticar(self.encargado)
        respuesta = self.client.post(f"/api/reservas/{reserva_id}/confirmar-pago/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["estado"], "PAGADA")
        self.assertEqual(respuesta.data["confirmada_por"]["username"], "encargado")

    def test_un_cliente_no_puede_confirmar_su_propio_pago(self):
        reserva_id = self.crear_pendiente()
        respuesta = self.client.post(f"/api/reservas/{reserva_id}/confirmar-pago/")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Reserva.objects.get(pk=reserva_id).estado, "PENDIENTE_PAGO")

    def test_no_se_confirma_dos_veces(self):
        reserva_id = self.crear_pendiente()
        self.autenticar(self.encargado)
        self.client.post(f"/api/reservas/{reserva_id}/confirmar-pago/")
        respuesta = self.client.post(f"/api/reservas/{reserva_id}/confirmar-pago/")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["regla"], "RN-03")

    def test_el_administrador_cancela_y_libera_el_bloque(self):
        reserva_id = self.crear_pendiente()
        self.autenticar(self.encargado)
        respuesta = self.client.post(f"/api/reservas/{reserva_id}/cancelar/")
        self.assertEqual(respuesta.data["estado"], "CANCELADA")
        self.autenticar(self.otro_cliente)
        self.assertEqual(self.solicitar().status_code, status.HTTP_201_CREATED)


class AislamientoEntreClientes(BaseAPI):
    """RN-08: cada cliente ve lo suyo; el administrador ve todo."""

    def setUp(self):
        super().setUp()
        self.autenticar(self.cliente)
        self.mia = self.solicitar(horas=3).data["id"]
        self.autenticar(self.otro_cliente)
        self.ajena = self.solicitar(horas=5).data["id"]

    def test_el_cliente_solo_lista_sus_reservas(self):
        self.autenticar(self.cliente)
        ids = [r["id"] for r in self.client.get("/api/reservas/").data["results"]]
        self.assertEqual(ids, [self.mia])

    def test_el_cliente_no_puede_leer_la_reserva_de_otro(self):
        self.autenticar(self.cliente)
        self.assertEqual(self.client.get(f"/api/reservas/{self.ajena}/").status_code, 404)

    def test_el_administrador_ve_todas(self):
        self.autenticar(self.encargado)
        ids = sorted(r["id"] for r in self.client.get("/api/reservas/").data["results"])
        self.assertEqual(ids, sorted([self.mia, self.ajena]))

    def test_el_administrador_filtra_por_estado(self):
        self.autenticar(self.encargado)
        self.client.post(f"/api/reservas/{self.mia}/confirmar-pago/")
        pendientes = self.client.get("/api/reservas/?estado=PENDIENTE_PAGO").data["results"]
        self.assertEqual([r["id"] for r in pendientes], [self.ajena])


class FaltasPorAPI(BaseAPI):
    """M-14 y M-15."""

    def setUp(self):
        super().setUp()
        for cliente, cantidad in ((self.cliente, 2), (self.otro_cliente, 5)):
            for numero in range(cantidad):
                momento = timezone.now() - timedelta(days=numero + 1)
                reserva = Reserva.objects.create(
                    cancha=self.cancha,
                    cliente=cliente,
                    inicio=momento,
                    fin=momento + timedelta(hours=1),
                    estado=Reserva.Estado.VENCIDA,
                    precio=1000,
                    vence_en=momento,
                )
                Falta.objects.create(cliente=cliente, reserva=reserva, motivo="prueba")

    def test_un_cliente_no_ve_el_panel_de_faltas(self):
        self.autenticar(self.cliente)
        self.assertEqual(self.client.get("/api/faltas/").status_code, 403)
        self.assertEqual(self.client.get("/api/faltas/resumen/").status_code, 403)

    def test_el_resumen_ordena_de_mas_a_menos_faltas(self):
        self.autenticar(self.encargado)
        datos = self.client.get("/api/faltas/resumen/").data
        self.assertEqual(datos["limite_faltas"], reglas.FALTAS_PARA_BLOQUEO)
        self.assertEqual([c["username"] for c in datos["clientes"]], ["drojas", "cmunoz"])
        self.assertEqual([c["total_faltas"] for c in datos["clientes"]], [5, 2])

    def test_el_detalle_de_faltas_trae_la_cancha(self):
        self.autenticar(self.encargado)
        faltas = self.client.get("/api/faltas/").data["results"]
        self.assertEqual(len(faltas), 7)
        self.assertEqual(faltas[0]["cancha"], "Cancha 1")

    def test_desbloquear_habilita_y_anula_las_faltas(self):
        servicios.desbloquear  # el caso de uso vive en el dominio
        for numero in range(5):
            momento = timezone.now() - timedelta(days=numero + 20)
            reserva = Reserva.objects.create(
                cancha=self.cancha,
                cliente=self.otro_cliente,
                inicio=momento,
                fin=momento + timedelta(hours=1),
                estado=Reserva.Estado.VENCIDA,
                precio=1000,
                vence_en=momento,
            )
            Falta.objects.create(cliente=self.otro_cliente, reserva=reserva, motivo="prueba")
        servicios.evaluar_bloqueo(self.otro_cliente)
        self.otro_cliente.refresh_from_db()
        self.assertTrue(self.otro_cliente.bloqueado)

        self.autenticar(self.encargado)
        respuesta = self.client.post(f"/api/clientes/{self.otro_cliente.pk}/desbloquear/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.data["bloqueado"])
        self.assertEqual(respuesta.data["faltas_vigentes"], 0)

    def test_un_cliente_no_puede_desbloquearse_a_si_mismo(self):
        self.autenticar(self.cliente)
        respuesta = self.client.post(f"/api/clientes/{self.cliente.pk}/desbloquear/")
        self.assertEqual(respuesta.status_code, 403)


class VencimientoPorAPI(BaseAPI):
    """M-13 · RN-04: el barrido perezoso también corre desde la API."""

    def test_consultar_la_agenda_vence_las_reservas_impagas(self):
        self.autenticar(self.cliente)
        reserva_id = self.solicitar().data["id"]
        Reserva.objects.filter(pk=reserva_id).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        self.client.credentials()
        self.client.get("/api/agenda/")

        reserva = Reserva.objects.get(pk=reserva_id)
        self.assertEqual(reserva.estado, Reserva.Estado.VENCIDA)
        self.assertEqual(Falta.objects.filter(cliente=self.cliente).count(), 1)

    def test_el_perfil_refleja_la_falta_recien_registrada(self):
        self.autenticar(self.cliente)
        reserva_id = self.solicitar().data["id"]
        Reserva.objects.filter(pk=reserva_id).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        perfil = self.client.get("/api/auth/yo/").data
        self.assertEqual(perfil["faltas_vigentes"], 1)
        self.assertEqual(perfil["faltas_restantes"], reglas.FALTAS_PARA_BLOQUEO - 1)
