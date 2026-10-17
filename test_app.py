import io
import os
import tempfile
import unittest
from PIL import Image
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import create_app
from database import get_db


class DevArcadeFullTestSuite(unittest.TestCase):
    def setUp(self):
        smtp_patch = patch.dict(os.environ, {'SMTP_HOST':''})
        smtp_patch.start()
        self.addCleanup(smtp_patch.stop)
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.upload_dir = tempfile.mkdtemp()
        self.app = create_app({
            "TESTING": True,
            "DB_PATH": self.db_path,
            "UPLOAD_FOLDER": self.upload_dir,
            "SECRET_KEY": "test-secret-suite",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO usuarios "
                "(nombre_jugador, email, password_hash, rol) "
                "VALUES (?, ?, ?, 'admin')",
                (
                    "admin_principal",
                    "admin@devarcade.dev",
                    generate_password_hash("admin1234"),
                ),
            )
            db.execute(
                "INSERT INTO usuarios "
                "(nombre_jugador, email, password_hash, rol) "
                "VALUES (?, ?, ?, 'admin')",
                (
                    "admin_auxiliar",
                    "aux@devarcade.dev",
                    generate_password_hash("admin1234"),
                ),
            )
            db.execute(
                "INSERT INTO proyectos "
                "(titulo, slug, descripcion, tecnologias, tipo, publicado) "
                "VALUES (?, ?, ?, ?, 'demo', 1)",
                (
                    "Snake",
                    "snake",
                    "Juego clásico Snake en Canvas con niveles.",
                    "JS, Canvas",
                ),
            )
            db.commit()

            for titulo, slug in [('Memory','memory'),('Ta-Te-Ti','ta-te-ti')]:
                db.execute("INSERT INTO proyectos(titulo,slug,descripcion,tipo,publicado) VALUES (?,?,?,'demo',1)",
                           (titulo,slug,'Demo de prueba automatizada.'))
            db.commit()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        for f in os.listdir(self.upload_dir):
            os.unlink(os.path.join(self.upload_dir, f))
        os.rmdir(self.upload_dir)

    def _csrf(self):
        res = self.client.get("/api/auth/me")
        return {"X-CSRF-Token": res.get_json()["csrf_token"]}

    def _login(self, email, password):
        headers = self._csrf()
        r = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        return {"X-CSRF-Token": r.get_json()["csrf_token"]}

    def test_1_seguridad_rutas_y_csrf(self):
        # Sin CSRF rechaza POST
        r_no_csrf = self.client.post("/api/visitas")
        self.assertEqual(r_no_csrf.status_code, 403)

        # Visitante no accede a juegos ni admin
        self.assertEqual(self.client.get("/juegos/snake.html").status_code, 302)
        self.assertEqual(self.client.get("/juegos/juego.js").status_code, 401)
        self.assertEqual(self.client.get("/admin.html").status_code, 302)
        self.assertEqual(self.client.get("/prototipo/admin.html").status_code, 302)

    def test_2_circuito_jugador_demos_puntajes_y_historial(self):
        h = self._csrf()
        r_reg = self.client.post(
            "/api/auth/registro",
            json={
                "nombre": "lucia_gamer",
                "email": "lucia@test.com",
                "password": "password123",
            },
            headers=h,
        )
        self.assertEqual(r_reg.status_code, 201)
        h = {"X-CSRF-Token": r_reg.get_json()["csrf_token"]}

        # Entra a los 3 juegos reales y verifica que el HTML incluye controles clave
        for ruta, marcador in [
            ("/juegos/snake.html", b"alternarPausa"),
            ("/juegos/memory.html", b"timeoutVolteo"),
            ("/juegos/tateti.html", b"minimax"),
        ]:
            resp = self.client.get(ruta)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(marcador, resp.data)
            resp.close()

        # Guarda puntajes en los 3 juegos e intenta un juego inexistente
        for juego, pts in [("snake", 120), ("memory", 950), ("ta-te-ti", 500)]:
            r_p = self.client.post(
                "/api/partidas",
                json={"juego": juego, "puntaje": pts},
                headers=h,
            )
            self.assertEqual(r_p.status_code, 201)

        r_invalido = self.client.post(
            "/api/partidas",
            json={"juego": "breakout", "puntaje": 300},
            headers=h,
        )
        self.assertEqual(r_invalido.status_code, 400)

        # Verifica historial propio y ranking
        mias = self.client.get("/api/partidas/mias").get_json()["partidas"]
        self.assertEqual(len(mias), 3)

    def test_3_crud_completo_proyectos_y_servicios(self):
        h = self._login("admin@devarcade.dev", "admin1234")

        # Crear proyecto en borrador
        r_create = self.client.post(
            "/api/proyectos",
            json={
                "titulo": "Nuevo Proyecto",
                "slug": "nuevo-proyecto",
                "descripcion": "Descripción técnica de al menos diez caracteres.",
                "tecnologias": "Python, Flask",
                "tipo": "proyecto",
                "orden": 5,
                "publicado": 0,
            },
            headers=h,
        )
        self.assertEqual(r_create.status_code, 201)
        proy_id = r_create.get_json()["id"]

        # El listado público oculta borradores, pero ?all=1 de admin lo incluye
        pub_slugs = [
            p["slug"]
            for p in self.client.get("/api/proyectos").get_json()["proyectos"]
        ]
        self.assertNotIn("nuevo-proyecto", pub_slugs)

        adm_slugs = [
            p["slug"]
            for p in self.client.get("/api/proyectos?all=1").get_json()["proyectos"]
        ]
        self.assertIn("nuevo-proyecto", adm_slugs)

        # Editar proyecto a publicado=1
        r_upd = self.client.put(
            f"/api/proyectos/{proy_id}",
            json={
                "titulo": "Nuevo Proyecto Publicado",
                "slug": "nuevo-proyecto",
                "descripcion": "Descripción actualizada y publicada.",
                "tecnologias": "Python, Flask, SQLite",
                "tipo": "proyecto",
                "orden": 2,
                "publicado": 1,
            },
            headers=h,
        )
        self.assertEqual(r_upd.status_code, 200)

        # Eliminar proyecto
        r_del = self.client.delete(f"/api/proyectos/{proy_id}", headers=h)
        self.assertEqual(r_del.status_code, 200)

        # CRUD completo de Servicio (Crear -> Editar -> Borrar)
        r_sc = self.client.post(
            "/api/servicios",
            json={
                "titulo": "Consultoría SQL",
                "descripcion": "Optimización de esquemas e índices relacionales.",
                "icono": "📊",
                "precio_estimado": "USD 150",
                "activo": 1,
            },
            headers=h,
        )
        self.assertEqual(r_sc.status_code, 201)
        serv_id = r_sc.get_json()["id"]

        r_su = self.client.put(
            f"/api/servicios/{serv_id}",
            json={
                "titulo": "Consultoría SQL Avanzada",
                "descripcion": "Optimización de esquemas e índices relacionales.",
                "icono": "📊",
                "precio_estimado": "USD 220",
                "activo": 0,
            },
            headers=h,
        )
        self.assertEqual(r_su.status_code, 200)
        self.assertEqual(
            self.client.delete(f"/api/servicios/{serv_id}", headers=h).status_code,
            200,
        )

    def test_4_subida_y_validacion_binaria_de_imagenes(self):
        h = self._login("admin@devarcade.dev", "admin1234")

        # PNG válido (firma mágica \x89PNG\r\n\x1a\n)
        png = io.BytesIO()
        Image.new('RGB', (2, 2), 'cyan').save(png, format='PNG')
        png_bytes = png.getvalue()
        data_ok = {"imagen": (io.BytesIO(png_bytes), "captura.png")}
        r_ok = self.client.post(
            "/api/proyectos/upload-imagen",
            data=data_ok,
            headers=h,
            content_type="multipart/form-data",
        )
        self.assertEqual(r_ok.status_code, 201)
        ruta_img = r_ok.get_json()["imagen"]
        with self.client.get(ruta_img) as response:
            self.assertEqual(response.status_code, 200)

        # Archivo falso (extensión .png pero contenido texto plano) -> 400
        fake_bytes = b"esto no es un png real"
        data_bad = {"imagen": (io.BytesIO(fake_bytes), "trampa.png")}
        r_bad = self.client.post(
            "/api/proyectos/upload-imagen",
            data=data_bad,
            headers=h,
            content_type="multipart/form-data",
        )
        self.assertEqual(r_bad.status_code, 400)

    def test_5_borrado_de_admin_que_respondio_consultas(self):
        # 1. Crear mensaje público
        h_pub = self._csrf()
        r_msg = self.client.post(
            "/api/mensajes",
            json={
                "nombre": "Ana",
                "email": "ana@mail.com",
                "tipo": "consulta",
                "mensaje": "Hola, tengo una consulta sobre tiempos de entrega.",
            },
            headers=h_pub,
        )
        msg_id = r_msg.get_json()["id"]

        # 2. El admin_auxiliar inicia sesión y responde la consulta
        h_aux = self._login("aux@devarcade.dev", "admin1234")
        r_resp = self.client.post(
            f"/api/mensajes/{msg_id}/responder",
            json={"cuerpo": "Te respondemos desde la cuenta auxiliar."},
            headers=h_aux,
        )
        self.assertEqual(r_resp.status_code, 200)

        # 3. El admin_principal inicia sesión y elimina a admin_auxiliar
        h_main = self._login("admin@devarcade.dev", "admin1234")
        usuarios = self.client.get("/api/usuarios").get_json()["usuarios"]
        aux_id = next(u["id"] for u in usuarios if u["email"] == "aux@devarcade.dev")

        r_del_admin = self.client.delete(f"/api/usuarios/{aux_id}", headers=h_main)
        self.assertEqual(r_del_admin.status_code, 200)

        # 4. El hilo de la consulta sigue intacto y conserva el nombre 'admin_auxiliar'
        hilo = self.client.get(f"/api/mensajes/{msg_id}").get_json()
        self.assertEqual(len(hilo["respuestas"]), 1)
        self.assertEqual(hilo["respuestas"][0]["admin_nombre"], "admin_auxiliar")
        self.assertIsNone(hilo["respuestas"][0]["admin_id"])

    def test_6_metricas_filtros_fechas_y_aviso_fallo_smtp(self):
        # Simular fallo de SMTP al enviar formulario de contacto
        h = self._csrf()
        with patch.dict(os.environ, {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": "9999"}):
            r_msg = self.client.post(
                "/api/mensajes",
                json={
                    "nombre": "Carlos",
                    "email": "carlos@mail.com",
                    "tipo": "asesoria",
                    "mensaje": "Prueba de fallo de acuse SMTP.",
                },
                headers=h,
            )
            self.assertEqual(r_msg.status_code, 201)
            payload = r_msg.get_json()
            self.assertEqual(payload["modo_envio"], "fallido")
            self.assertIsNotNone(payload["aviso_correo"])

        # Verificar filtros de fecha en /api/stats (incluyendo topJugadores)
        h_adm = self._login("admin@devarcade.dev", "admin1234")
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO partidas (usuario_id, juego, puntaje, jugado_en) "
                "VALUES (1, 'snake', 800, '2020-01-05 12:00:00')"
            )
            db.commit()

        # En los últimos 7 días no debe aparecer la partida de 2020
        s_reciente = self.client.get("/api/stats?dias=7").get_json()
        self.assertEqual(len(s_reciente["topJugadores"]), 0)

        # Filtrando por rango 2020-01-01 a 2020-01-10 sí aparece
        s_2020 = self.client.get(
            "/api/stats?desde=2020-01-01&hasta=2020-01-10"
        ).get_json()
        self.assertEqual(len(s_2020["topJugadores"]), 1)
        self.assertEqual(s_2020["topJugadores"][0]["mejor"], 800)


    def test_7_suspension_revoca_sesion_y_reintentos_no_duplican(self):
        h = self._csrf()
        r = self.client.post('/api/auth/registro', json={
            'nombre':'jugador_retry','email':'retry@test.com','password':'password123'}, headers=h)
        usuario_id = r.json['usuario']['id']
        h = {'X-CSRF-Token':r.json['csrf_token']}
        resultado = {'juego':'snake','puntaje':100,'resultado_id':'partida-reintento-123'}
        a = self.client.post('/api/partidas',json=resultado,headers=h)
        b = self.client.post('/api/partidas',json=resultado,headers=h)
        self.assertEqual(a.status_code,201)
        self.assertEqual(b.status_code,200)
        self.assertEqual(a.json['id'],b.json['id'])
        self.assertEqual(len(self.client.get('/api/partidas/mias').json['partidas']),1)
        with self.app.app_context():
            db=get_db();db.execute('UPDATE usuarios SET activo=0 WHERE id=?',(usuario_id,));db.commit()
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.assertEqual(self.client.post('/api/partidas',json=resultado,headers=h).status_code,401)

    def test_8_seed_idempotente_y_validaciones(self):
        from seed import run_seed
        run_seed(self.app)
        with self.app.app_context():
            before = {t:get_db().execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                      for t in ('usuarios','proyectos','servicios','visitas','partidas')}
        run_seed(self.app)
        with self.app.app_context():
            after = {t:get_db().execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in before}
        self.assertEqual(before,after)
        h=self._login('admin@devarcade.dev','admin1234')
        self.assertEqual(self.client.get('/api/stats?desde=2026-10-10').status_code,400)
        self.assertEqual(self.client.get('/api/stats?desde=2026-10-10&hasta=2026-10-01').status_code,400)
        self.assertEqual(self.client.post('/api/partidas',json={'juego':'snake','puntaje':1.5},headers=h).status_code,400)
        self.assertEqual(self.client.post('/api/mensajes',json=['no-es-objeto'],headers=h).status_code,400)

    def test_9_fallo_smtp_respuesta_queda_registrado(self):
        h=self._csrf()
        with patch.dict(os.environ,{'SMTP_HOST':''}):
            r=self.client.post('/api/mensajes',json={'nombre':'Cliente','email':'cliente@test.com',
                 'tipo':'consulta','mensaje':'Consulta de prueba de correo.'},headers=h)
        mid=r.json['id'];h=self._login('admin@devarcade.dev','admin1234')
        with patch.dict(os.environ,{'SMTP_HOST':'correo.test'}), patch('app.smtplib.SMTP',side_effect=OSError('fallo simulado')):
            r=self.client.post(f'/api/mensajes/{mid}/responder',json={'cuerpo':'Respuesta de prueba'},headers=h)
        self.assertEqual(r.status_code,502)
        hilo=self.client.get(f'/api/mensajes/{mid}').json
        self.assertEqual(hilo['mensaje']['estado'],'error_envio')
        self.assertEqual(hilo['respuestas'][0]['modo_envio'],'fallido')

    def test_10_formularios_html_conectados_al_cliente(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__();self.ids=set();self.forms=0
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if 'id' in attrs:self.ids.add(attrs['id'])
                if tag=='form':self.forms+=1
        for ruta,ids in [('/',{'form-contacto','lista-servicios','nombre','email','tipo','mensaje'}),
                         ('/login.html',{'tab-login','tab-registro','login-email','login-pass','reg-user','reg-email','reg-pass','reg-pass2'}),
                         ('/arcade.html',{'grilla-maquinas','tabla-ranking-sala'})]:
            with self.client.get(ruta) as response:
                parser=Forms();parser.feed(response.text);self.assertTrue(ids <= parser.ids)
                if ruta=='/login.html':self.assertEqual(parser.forms,2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
