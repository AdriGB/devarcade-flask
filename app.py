import os
import secrets
import smtplib
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from email.message import EmailMessage
from functools import wraps
from dotenv import load_dotenv
from flask import (
    Flask, Blueprint, request, jsonify, session, g,
    send_from_directory, redirect, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_db, close_db, init_schema, row_to_dict, rows_to_list
from validators import (
    ValidationError, v_str, v_nombre_jugador, v_email,
    v_slug, v_int, v_bool_int, v_one_of, v_date, v_imagen_archivo
)

load_dotenv(Path(__file__).resolve().parent / '.env')

JUEGOS_IMPLEMENTADOS = {
    "snake": "/juegos/snake.html",
    "memory": "/juegos/memory.html",
    "ta-te-ti": "/juegos/tateti.html",
}

LIMITES_PUNTAJE = {
    "snake": 10000,
    "memory": 1500,
    "ta-te-ti": 50000,
}


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    secret_path = Path(app.root_path) / '.secret_key'
    secret = os.environ.get('FLASK_SECRET_KEY')
    if not secret:
        if not secret_path.exists():
            secret_path.write_text(secrets.token_hex(32), encoding='utf-8')
        secret = secret_path.read_text(encoding='utf-8').strip()
    default_db = os.path.join(
        app.root_path, os.environ.get("DB_PATH", "db/devarcade.db")
    )
    app.config.update(
        SECRET_KEY=secret,
        DB_PATH=default_db,
        UPLOAD_FOLDER=os.path.join(app.root_path, "uploads"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=3 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.teardown_appcontext(close_db)
    init_schema(app)

    @app.before_request
    def cargar_usuario_y_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(24)

        g.usuario = None
        if request.path.startswith('/api/') and request.is_json:
            payload = request.get_json(silent=True)
            if payload is not None and not isinstance(payload, dict):
                return jsonify(error='El cuerpo JSON debe ser un objeto'), 400
        user_id = session.get("user_id")
        if user_id is not None:
            db = get_db()
            sql_u = (
                "SELECT id, nombre_jugador, email, rol, activo "
                "FROM usuarios WHERE id = ?"
            )
            u = db.execute(sql_u, (user_id,)).fetchone()
            if u and u["activo"] == 1:
                g.usuario = {
                    "id": u["id"],
                    "nombre": u["nombre_jugador"],
                    "email": u["email"],
                    "rol": u["rol"],
                }
            else:
                session.pop("user_id", None)

        metodos_mutables = ("POST", "PUT", "DELETE", "PATCH")
        if request.path.startswith("/api/") and request.method in metodos_mutables:
            token_header = request.headers.get("X-CSRF-Token")
            if not token_header or token_header != session.get("csrf_token"):
                return jsonify({
                    "error": "Token CSRF inválido o ausente. Recargá la página."
                }), 403

    @app.after_request
    def inyectar_cookie_csrf(response):
        if g.get('usuario') or request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if "csrf_token" in session:
            response.set_cookie(
                "csrf_token",
                session["csrf_token"],
                httponly=False,
                samesite="Lax",
            )
        return response

    def require_login(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not g.usuario:
                return jsonify({"error": "Iniciá sesión para continuar"}), 401
            return f(*args, **kwargs)
        return wrapper

    def require_admin(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not g.usuario:
                return jsonify({"error": "Iniciá sesión para continuar"}), 401
            if g.usuario["rol"] != "admin":
                return jsonify({
                    "error": "Se requieren permisos de administrador"
                }), 403
            return f(*args, **kwargs)
        return wrapper

    def registrar_acceso(usuario_id, evento="login", recurso=None):
        db = get_db()
        db.execute(
            "INSERT INTO accesos_usuarios (usuario_id, evento, recurso) "
            "VALUES (?, ?, ?)",
            (usuario_id, evento, recurso),
        )
        db.commit()

    # ========================================================
    # 1. AUTH (/api/auth)
    # ========================================================
    bp_auth = Blueprint("auth", __name__, url_prefix="/api/auth")

    @bp_auth.post("/registro")
    def registro():
        data = request.get_json(silent=True) or {}
        try:
            nombre = v_nombre_jugador(data.get("nombre"))
            email = v_email(data.get("email"))
            password = v_str(
                data.get("password"), field="password", min_len=8, max_len=72
            )
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        existe = db.execute(
            "SELECT id FROM usuarios "
            "WHERE email = ? OR lower(nombre_jugador) = lower(?)",
            (email, nombre),
        ).fetchone()
        if existe:
            return jsonify({
                "error": "Ese email o nombre de jugador ya está registrado"
            }), 409

        pw_hash = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO usuarios (nombre_jugador, email, password_hash, rol) "
            "VALUES (?, ?, ?, 'user')",
            (nombre, email, pw_hash),
        )
        user_id = cur.lastrowid
        db.commit()

        session.clear()
        session['csrf_token'] = secrets.token_hex(24)
        session["user_id"] = user_id
        registrar_acceso(user_id, "registro", "auth/registro")
        usuario = {
            "id": user_id, "nombre": nombre, "email": email, "rol": "user"
        }
        return jsonify({
            "ok": True,
            "usuario": usuario,
            "csrf_token": session["csrf_token"],
        }), 201

    @bp_auth.post("/login")
    def login():
        data = request.get_json(silent=True) or {}
        try:
            email = v_email(data.get("email"))
            password = v_str(
                data.get("password"), field="password", min_len=1, max_len=72
            )
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        user = db.execute(
            "SELECT * FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Email o contraseña incorrectos"}), 401
        if user["activo"] == 0:
            return jsonify({
                "error": "Esta cuenta se encuentra suspendida"
            }), 403

        session.clear()
        session['csrf_token'] = secrets.token_hex(24)
        session["user_id"] = user["id"]
        registrar_acceso(user["id"], "login", "auth/login")
        usuario = {
            "id": user["id"],
            "nombre": user["nombre_jugador"],
            "email": user["email"],
            "rol": user["rol"],
        }
        return jsonify({
            "ok": True,
            "usuario": usuario,
            "csrf_token": session["csrf_token"],
        })

    @bp_auth.post("/logout")
    @require_login
    def logout():
        session.clear()
        session["csrf_token"] = secrets.token_hex(24)
        return jsonify({"ok": True, "csrf_token": session["csrf_token"]})

    @bp_auth.get("/me")
    def me():
        if not g.usuario:
            return jsonify({
                "error": "Sin sesión activa",
                "csrf_token": session.get("csrf_token"),
            }), 401
        return jsonify({
            "usuario": g.usuario,
            "csrf_token": session.get("csrf_token"),
        })

    # ========================================================
    # 2. PROYECTOS (/api/proyectos)
    # ========================================================
    bp_proyectos = Blueprint("proyectos", __name__, url_prefix="/api/proyectos")

    def enriquecer_proyecto_publico(p, autenticado=False):
        item = dict(p)
        slug = item["slug"]
        item["jugable"] = slug in JUEGOS_IMPLEMENTADOS
        if autenticado:
            item["demo_url"] = (
                JUEGOS_IMPLEMENTADOS.get(slug) or item.get("demo_url")
            )
        else:
            desc = item.get("descripcion") or ""
            item["descripcion"] = desc[:115] + ("…" if len(desc) > 115 else "")
            item.pop("tecnologias", None)
            item.pop("demo_url", None)
        return item

    @bp_proyectos.get("")
    def listar_proyectos():
        db = get_db()
        es_admin_view = (
            request.args.get("all") == "1"
            and g.usuario
            and g.usuario["rol"] == "admin"
        )
        if es_admin_view:
            filas = db.execute(
                "SELECT * FROM proyectos ORDER BY orden ASC, id ASC"
            ).fetchall()
            lista = []
            for f in filas:
                d = dict(f)
                d["jugable"] = d["slug"] in JUEGOS_IMPLEMENTADOS
                lista.append(d)
            return jsonify({"proyectos": lista})

        filas = db.execute(
            "SELECT id, titulo, slug, descripcion, tecnologias, imagen, "
            "demo_url, tipo, orden, destacado, publicado "
            "FROM proyectos WHERE publicado = 1 ORDER BY orden ASC, id ASC"
        ).fetchall()
        autenticado = g.usuario is not None
        return jsonify({
            "proyectos": [
                enriquecer_proyecto_publico(f, autenticado) for f in filas
            ]
        })

    @bp_proyectos.get("/<slug>")
    @require_login
    def detalle_proyecto(slug):
        db = get_db()
        p = db.execute(
            "SELECT * FROM proyectos WHERE slug = ?", (slug,)
        ).fetchone()
        if not p or (p["publicado"] == 0 and g.usuario["rol"] != "admin"):
            return jsonify({"error": "Proyecto no encontrado"}), 404
        d = dict(p)
        d["jugable"] = d["slug"] in JUEGOS_IMPLEMENTADOS
        d["demo_url"] = (
            JUEGOS_IMPLEMENTADOS.get(d["slug"]) or d.get("demo_url")
        )
        return jsonify({"proyecto": d})

    def validar_proyecto_payload(data):
        titulo = v_str(data.get("titulo"), field="titulo", min_len=2, max_len=80)
        slug = v_slug(data.get("slug") or titulo, field="slug")
        descripcion = v_str(
            data.get("descripcion"),
            field="descripcion",
            min_len=10,
            max_len=2000,
        )
        tecnologias = v_str(
            data.get("tecnologias"),
            field="tecnologias",
            max_len=300,
            allow_empty=True,
        ) or None
        imagen = v_str(
            data.get("imagen"), field="imagen", max_len=300, allow_empty=True
        ) or None
        demo_url = v_str(
            data.get("demo_url"),
            field="demo_url",
            max_len=300,
            allow_empty=True,
        ) or None
        if imagen and not imagen.startswith('/uploads/'):
            raise ValidationError('imagen: usá una imagen subida desde el panel')
        if demo_url:
            parts = urlsplit(demo_url)
            if parts.scheme or parts.netloc or not demo_url.startswith('/juegos/'):
                raise ValidationError('demo_url: debe ser una ruta local de juegos')
        tipo = v_one_of(
            data.get("tipo", "demo"), ["proyecto", "demo"], field="tipo"
        )
        orden = v_int(
            data.get("orden", 0), field="orden", min_val=0, max_val=999
        )
        destacado = v_bool_int(data.get("destacado"), default=0)
        publicado = v_bool_int(data.get("publicado"), default=1)
        return {
            "titulo": titulo,
            "slug": slug,
            "descripcion": descripcion,
            "tecnologias": tecnologias,
            "imagen": imagen,
            "demo_url": demo_url,
            "tipo": tipo,
            "orden": orden,
            "destacado": destacado,
            "publicado": publicado,
        }

    @bp_proyectos.post("")
    @require_admin
    def crear_proyecto():
        data = request.get_json(silent=True) or {}
        try:
            p = validar_proyecto_payload(data)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        existe = db.execute(
            "SELECT id FROM proyectos WHERE slug = ?", (p["slug"],)
        ).fetchone()
        if existe:
            return jsonify({"error": "Ya existe un proyecto con ese slug"}), 409

        cur = db.execute(
            "INSERT INTO proyectos "
            "(titulo, slug, descripcion, tecnologias, imagen, demo_url, "
            "tipo, orden, destacado, publicado) VALUES "
            "(:titulo, :slug, :descripcion, :tecnologias, :imagen, :demo_url, "
            ":tipo, :orden, :destacado, :publicado)",
            p,
        )
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201

    @bp_proyectos.put("/<int:id>")
    @require_admin
    def editar_proyecto(id):
        data = request.get_json(silent=True) or {}
        try:
            p = validar_proyecto_payload(data)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        dup = db.execute(
            "SELECT id FROM proyectos WHERE slug = ? AND id != ?",
            (p["slug"], id),
        ).fetchone()
        if dup:
            return jsonify({"error": "Otro proyecto ya usa ese slug"}), 409

        p["id"] = id
        cur = db.execute(
            "UPDATE proyectos SET "
            "titulo=:titulo, slug=:slug, descripcion=:descripcion, "
            "tecnologias=:tecnologias, imagen=:imagen, demo_url=:demo_url, "
            "tipo=:tipo, orden=:orden, destacado=:destacado, "
            "publicado=:publicado WHERE id=:id",
            p,
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Proyecto no encontrado"}), 404
        return jsonify({"ok": True})

    @bp_proyectos.delete("/<int:id>")
    @require_admin
    def borrar_proyecto(id):
        db = get_db()
        cur = db.execute("DELETE FROM proyectos WHERE id = ?", (id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Proyecto no encontrado"}), 404
        return jsonify({"ok": True})

    @bp_proyectos.post("/upload-imagen")
    @require_admin
    def subir_imagen_proyecto():
        archivo = request.files.get("imagen")
        try:
            ext = v_imagen_archivo(archivo)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        nombre_seguro = secure_filename(f"proy_{uuid.uuid4().hex[:12]}{ext}")
        ruta_destino = os.path.join(app.config["UPLOAD_FOLDER"], nombre_seguro)
        archivo.save(ruta_destino)
        return jsonify({"ok": True, "imagen": f"/uploads/{nombre_seguro}"}), 201

    # ========================================================
    # 3. SERVICIOS (/api/servicios)
    # ========================================================
    bp_servicios = Blueprint("servicios", __name__, url_prefix="/api/servicios")

    @bp_servicios.get("")
    def listar_servicios():
        db = get_db()
        es_admin_view = (
            request.args.get("all") == "1"
            and g.usuario
            and g.usuario["rol"] == "admin"
        )
        sql = (
            "SELECT * FROM servicios ORDER BY id ASC"
            if es_admin_view
            else "SELECT * FROM servicios WHERE activo = 1 ORDER BY id ASC"
        )
        filas = db.execute(sql).fetchall()
        return jsonify({"servicios": rows_to_list(filas)})

    def validar_servicio_payload(data):
        titulo = v_str(data.get("titulo"), field="titulo", min_len=2, max_len=80)
        descripcion = v_str(
            data.get("descripcion"),
            field="descripcion",
            min_len=10,
            max_len=600,
        )
        icono = v_str(
            data.get("icono"), field="icono", max_len=50, allow_empty=True
        ) or "💻"
        precio = v_str(
            data.get("precio_estimado"),
            field="precio_estimado",
            max_len=50,
            allow_empty=True,
        ) or None
        activo = v_bool_int(data.get("activo"), default=1)
        return {
            "titulo": titulo,
            "descripcion": descripcion,
            "icono": icono,
            "precio_estimado": precio,
            "activo": activo,
        }

    @bp_servicios.post("")
    @require_admin
    def crear_servicio():
        data = request.get_json(silent=True) or {}
        try:
            s = validar_servicio_payload(data)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        dup = db.execute(
            "SELECT id FROM servicios WHERE lower(titulo) = lower(?)",
            (s["titulo"],),
        ).fetchone()
        if dup:
            return jsonify({"error": "Ya existe un servicio con ese título"}), 409

        cur = db.execute(
            "INSERT INTO servicios "
            "(titulo, descripcion, icono, precio_estimado, activo) "
            "VALUES (:titulo, :descripcion, :icono, :precio_estimado, :activo)",
            s,
        )
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201

    @bp_servicios.put("/<int:id>")
    @require_admin
    def editar_servicio(id):
        data = request.get_json(silent=True) or {}
        try:
            s = validar_servicio_payload(data)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        dup = db.execute(
            "SELECT id FROM servicios "
            "WHERE lower(titulo) = lower(?) AND id != ?",
            (s["titulo"], id),
        ).fetchone()
        if dup:
            return jsonify({"error": "Otro servicio ya tiene ese título"}), 409

        s["id"] = id
        cur = db.execute(
            "UPDATE servicios SET titulo=:titulo, descripcion=:descripcion, "
            "icono=:icono, precio_estimado=:precio_estimado, activo=:activo "
            "WHERE id=:id",
            s,
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Servicio no encontrado"}), 404
        return jsonify({"ok": True})

    @bp_servicios.delete("/<int:id>")
    @require_admin
    def borrar_servicio(id):
        db = get_db()
        cur = db.execute("DELETE FROM servicios WHERE id = ?", (id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Servicio no encontrado"}), 404
        return jsonify({"ok": True})

    # ========================================================
    # 4. MENSAJES (/api/mensajes)
    # ========================================================
    bp_mensajes = Blueprint("mensajes", __name__, url_prefix="/api/mensajes")
    MAPA_TIPOS_CONSULTA = {
        "consulta": "consulta",
        "consulta general": "consulta",
        "cotizacion": "cotizacion",
        "cotización": "cotizacion",
        "cotizacion de proyecto": "cotizacion",
        "cotización de proyecto": "cotizacion",
        "asesoria": "asesoria",
        "asesoría": "asesoria",
        "asesoria tecnica": "asesoria",
        "asesoría técnica": "asesoria",
    }

    def enviar_correo(destinatario, asunto, cuerpo):
        smtp_host = os.environ.get("SMTP_HOST", "").strip()
        if not smtp_host:
            return (
                "simulado",
                "Modo simulación local (SMTP_HOST no configurado en .env)",
            )

        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "").strip()
        smtp_pass = os.environ.get("SMTP_PASS", "").strip()
        smtp_from = os.environ.get(
            "SMTP_FROM", smtp_user or "no-reply@devarcade.dev"
        )

        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = smtp_from
        msg["To"] = destinatario
        msg.set_content(cuerpo)

        try:
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as srv:
                    if smtp_user:
                        srv.login(smtp_user, smtp_pass)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as srv:
                    srv.starttls()
                    if smtp_user:
                        srv.login(smtp_user, smtp_pass)
                    srv.send_message(msg)
            return "smtp", f"Entregado vía {smtp_host}:{smtp_port}"
        except Exception as exc:
            return "fallido", str(exc)

    @bp_mensajes.post("")
    def crear_mensaje():
        data = request.get_json(silent=True) or {}
        try:
            nombre = v_str(
                data.get("nombre"), field="nombre", min_len=2, max_len=80
            )
            email = v_email(data.get("email"))
            raw_tipo = v_str(
                data.get("tipo"), field="tipo", min_len=2, max_len=50
            ).lower()
            tipo = MAPA_TIPOS_CONSULTA.get(raw_tipo)
            if not tipo:
                raise ValidationError(
                    "tipo: seleccioná consulta, cotizacion o asesoria"
                )
            mensaje = v_str(
                data.get("mensaje"), field="mensaje", min_len=10, max_len=2000
            )
            asunto = v_str(
                data.get("asunto"),
                field="asunto",
                max_len=150,
                allow_empty=True,
            ) or f"Contacto ({tipo.capitalize()})"
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        cur = db.execute(
            "INSERT INTO mensajes (nombre, email, asunto, tipo, mensaje) "
            "VALUES (?, ?, ?, ?, ?)",
            (nombre, email, asunto, tipo, mensaje),
        )
        msg_id = cur.lastrowid
        db.commit()

        cuerpo_ack = (
            f"Hola {nombre},\n\n"
            f"Recibimos tu mensaje ({tipo}) en DevArcade:\n"
            f"\"{mensaje}\"\n\n"
            f"Te responderemos a la brevedad."
        )
        modo, detalle = enviar_correo(
            email, f"Recibimos tu consulta: {asunto}", cuerpo_ack
        )
        aviso_correo = None
        if modo == "fallido":
            aviso_correo = (
                "Tu consulta quedó guardada en la bandeja del administrador, "
                "pero el acuse automático por email falló."
            )

        return jsonify({
            "ok": True,
            "id": msg_id,
            "modo_envio": modo,
            "detalle_envio": detalle,
            "aviso_correo": aviso_correo,
        }), 201

    @bp_mensajes.get("")
    @require_admin
    def listar_mensajes():
        db = get_db()
        estado = request.args.get("estado")
        if estado in ("nuevo", "respondido", "error_envio"):
            mensajes = db.execute(
                "SELECT * FROM mensajes WHERE estado = ? "
                "ORDER BY creado_en DESC",
                (estado,),
            ).fetchall()
        else:
            mensajes = db.execute(
                "SELECT * FROM mensajes ORDER BY creado_en DESC"
            ).fetchall()
        resumen = db.execute(
            "SELECT estado, COUNT(*) AS total FROM mensajes GROUP BY estado"
        ).fetchall()
        return jsonify({
            "mensajes": rows_to_list(mensajes),
            "resumen": rows_to_list(resumen),
            "smtp_activo": bool(os.environ.get("SMTP_HOST", "").strip()),
        })

    @bp_mensajes.get("/<int:id>")
    @require_admin
    def detalle_mensaje(id):
        db = get_db()
        m = db.execute(
            "SELECT * FROM mensajes WHERE id = ?", (id,)
        ).fetchone()
        if not m:
            return jsonify({"error": "Mensaje no encontrado"}), 404
        # LEFT JOIN permite ver respuestas incluso si el admin que respondió fue borrado
        respuestas = db.execute(
            "SELECT r.id, r.mensaje_id, r.admin_id, r.cuerpo, "
            "r.modo_envio, r.detalle_envio, r.enviado_en, "
            "COALESCE(u.nombre_jugador, r.admin_nombre, 'admin') AS admin_nombre "
            "FROM respuestas r "
            "LEFT JOIN usuarios u ON u.id = r.admin_id "
            "WHERE r.mensaje_id = ? ORDER BY r.enviado_en ASC",
            (id,),
        ).fetchall()
        return jsonify({
            "mensaje": row_to_dict(m),
            "respuestas": rows_to_list(respuestas),
        })

    @bp_mensajes.post("/<int:id>/responder")
    @require_admin
    def responder_mensaje(id):
        data = request.get_json(silent=True) or {}
        try:
            cuerpo = v_str(
                data.get("cuerpo"), field="cuerpo", min_len=5, max_len=5000
            )
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        m = db.execute(
            "SELECT * FROM mensajes WHERE id = ?", (id,)
        ).fetchone()
        if not m:
            return jsonify({"error": "Mensaje no encontrado"}), 404

        modo, detalle = enviar_correo(
            m["email"],
            f"Re: {m['asunto'] or 'Tu consulta en DevArcade'}",
            cuerpo,
        )

        nuevo_estado = "error_envio" if modo == "fallido" else "respondido"
        db.execute(
            "INSERT INTO respuestas "
            "(mensaje_id, admin_id, admin_nombre, cuerpo, modo_envio, detalle_envio) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                id,
                g.usuario["id"],
                g.usuario["nombre"],
                cuerpo,
                modo,
                detalle,
            ),
        )
        db.execute(
            "UPDATE mensajes SET estado = ? WHERE id = ?", (nuevo_estado, id)
        )
        db.commit()

        if modo == "fallido":
            return jsonify({
                "ok": False,
                "error": (
                    f"Fallo al enviar por SMTP: {detalle}. "
                    "Se registró el intento."
                ),
                "modo_envio": modo,
            }), 502

        return jsonify({
            "ok": True,
            "estado": nuevo_estado,
            "modo_envio": modo,
            "detalle_envio": detalle,
        })

    # ========================================================
    # 5. PARTIDAS (/api/partidas)
    # ========================================================
    bp_partidas = Blueprint("partidas", __name__, url_prefix="/api/partidas")

    @bp_partidas.post("")
    @require_login
    def guardar_partida():
        data = request.get_json(silent=True) or {}
        try:
            juego = v_slug(data.get("juego"), field="juego")
            if juego not in JUEGOS_IMPLEMENTADOS:
                raise ValidationError(
                    f"juego: '{juego}' no es una demo interactiva habilitada"
                )
            max_pts = LIMITES_PUNTAJE.get(juego, 100000)
            puntaje = v_int(
                data.get("puntaje"), field="puntaje", min_val=0, max_val=max_pts
            )
            resultado_id = v_str(data.get('resultado_id'), field='resultado_id',
                                 min_len=8, max_len=80, allow_empty=True) or None
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        previo = db.execute('SELECT id,juego,puntaje FROM partidas WHERE usuario_id=? AND resultado_id=?',
                            (g.usuario['id'], resultado_id)).fetchone() if resultado_id else None
        if previo:
            if previo['juego'] != juego or previo['puntaje'] != puntaje:
                return jsonify(error='El resultado ya existe con otros datos'), 409
            return jsonify(ok=True, id=previo['id']), 200
        cur = db.execute(
            "INSERT INTO partidas (usuario_id, juego, puntaje, resultado_id) "
            "VALUES (?, ?, ?, ?)",
            (g.usuario["id"], juego, puntaje, resultado_id),
        )
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201

    @bp_partidas.get("/ranking")
    def obtener_ranking():
        try:
            limite = v_int(
                request.args.get("limite", 10),
                field="limite",
                min_val=1,
                max_val=100,
            )
            juego = (
                v_slug(request.args.get("juego"), field="juego")
                if request.args.get("juego")
                else None
            )
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        if juego:
            filas = db.execute(
                "SELECT u.nombre_jugador, ? AS juego, "
                "MAX(p.puntaje) AS mejor_puntaje, COUNT(p.id) AS partidas "
                "FROM partidas p JOIN usuarios u ON u.id = p.usuario_id "
                "WHERE p.juego = ? AND p.puntaje > 0 AND u.activo = 1 "
                "GROUP BY u.id ORDER BY mejor_puntaje DESC LIMIT ?",
                (juego, juego, limite),
            ).fetchall()
        else:
            filas = db.execute(
                "SELECT u.nombre_jugador, "
                "(SELECT p2.juego FROM partidas p2 "
                " WHERE p2.usuario_id = u.id "
                " ORDER BY p2.puntaje DESC LIMIT 1) AS juego, "
                "MAX(p.puntaje) AS mejor_puntaje, COUNT(p.id) AS partidas "
                "FROM partidas p JOIN usuarios u ON u.id = p.usuario_id "
                "WHERE p.puntaje > 0 AND u.activo = 1 "
                "GROUP BY u.id ORDER BY mejor_puntaje DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return jsonify({"ranking": rows_to_list(filas)})

    @bp_partidas.get("/mias")
    @require_login
    def mis_partidas():
        juego = request.args.get("juego")
        db = get_db()
        if juego:
            filas = db.execute(
                "SELECT * FROM partidas WHERE usuario_id = ? AND juego = ? "
                "ORDER BY jugado_en DESC LIMIT 50",
                (g.usuario["id"], juego),
            ).fetchall()
        else:
            filas = db.execute(
                "SELECT * FROM partidas WHERE usuario_id = ? "
                "ORDER BY jugado_en DESC LIMIT 50",
                (g.usuario["id"],),
            ).fetchall()
        return jsonify({"partidas": rows_to_list(filas)})

    # ========================================================
    # 6. USUARIOS (/api/usuarios - Admin CRUD)
    # ========================================================
    bp_usuarios = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

    @bp_usuarios.get("")
    @require_admin
    def listar_usuarios():
        db = get_db()
        filas = db.execute(
            "SELECT u.id, u.nombre_jugador AS nombre, u.email, u.rol, "
            "u.activo, u.creado_en, "
            "COUNT(DISTINCT p.id) AS partidas_jugadas, "
            "COALESCE(MAX(p.puntaje), 0) AS mejor_puntaje, "
            "(SELECT COUNT(*) FROM accesos_usuarios a "
            " WHERE a.usuario_id = u.id) AS total_accesos "
            "FROM usuarios u "
            "LEFT JOIN partidas p ON p.usuario_id = u.id "
            "GROUP BY u.id ORDER BY u.id ASC"
        ).fetchall()
        return jsonify({"usuarios": rows_to_list(filas)})

    @bp_usuarios.put("/<int:id>")
    @require_admin
    def actualizar_usuario(id):
        data = request.get_json(silent=True) or {}
        try:
            rol = v_one_of(data.get("rol", "user"), ["user", "admin"], field="rol")
            activo = v_bool_int(data.get("activo"), default=1)
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        if id == g.usuario["id"] and (rol != "admin" or activo == 0):
            return jsonify({
                "error": (
                    "No podés quitarte permisos de administrador "
                    "o desactivar tu propia cuenta"
                )
            }), 400

        db = get_db()
        cur = db.execute(
            "UPDATE usuarios SET rol = ?, activo = ? WHERE id = ?",
            (rol, activo, id),
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Usuario no encontrado"}), 404
        return jsonify({"ok": True})

    @bp_usuarios.delete("/<int:id>")
    @require_admin
    def eliminar_usuario(id):
        if id == g.usuario["id"]:
            return jsonify({
                "error": "No podés eliminar tu propia cuenta activa"
            }), 400

        db = get_db()
        u_target = db.execute(
            "SELECT id, nombre_jugador FROM usuarios WHERE id = ?", (id,)
        ).fetchone()
        if not u_target:
            return jsonify({"error": "Usuario no encontrado"}), 404

        try:
            # Desvincular respuestas previas conservando el nombre histórico del admin
            db.execute(
                "UPDATE respuestas SET admin_nombre = COALESCE(admin_nombre, ?), "
                "admin_id = NULL WHERE admin_id = ?",
                (u_target["nombre_jugador"], id),
            )
            db.execute("DELETE FROM usuarios WHERE id = ?", (id,))
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            return jsonify({
                "error": f"No se pudo eliminar el usuario por referencias activas: {exc}"
            }), 409

        return jsonify({"ok": True})

    # ========================================================
    # 7. STATS & MÉTRICAS (/api/stats)
    # ========================================================
    bp_stats = Blueprint("stats", __name__, url_prefix="/api/stats")

    @bp_stats.get("")
    @require_admin
    def obtener_stats():
        try:
            dias = v_int(
                request.args.get("dias", 14),
                field="dias",
                min_val=1,
                max_val=365,
            )
            desde = v_date(request.args.get("desde"), field="desde")
            hasta = v_date(request.args.get("hasta"), field="hasta")
            if bool(desde) != bool(hasta) or (desde and desde > hasta):
                raise ValidationError('fechas: indicá un rango completo y ordenado')
            juego = (
                v_slug(request.args.get("juego"), field="juego")
                if request.args.get("juego")
                else None
            )
            tipo_consulta = request.args.get("tipo")
            if tipo_consulta:
                v_one_of(
                    tipo_consulta,
                    ["consulta", "cotizacion", "asesoria"],
                    field="tipo",
                )
        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        db = get_db()
        if desde and hasta:
            cond_fecha_dt = "date(creado_en) BETWEEN ? AND ?"
            cond_fecha_vis = "fecha BETWEEN ? AND ?"
            cond_fecha_part = "date(p.jugado_en) BETWEEN ? AND ?"
            params_fecha = [desde, hasta]
        else:
            mod = f"-{dias} days"
            cond_fecha_dt = "date(creado_en) >= date('now', ?, 'localtime')"
            cond_fecha_vis = "fecha >= date('now', ?, 'localtime')"
            cond_fecha_part = "date(p.jugado_en) >= date('now', ?, 'localtime')"
            params_fecha = [mod]

        conteos = {
            "visitasTotales": db.execute(
                "SELECT COALESCE(SUM(contador), 0) AS n FROM visitas"
            ).fetchone()["n"],
            "usuariosRegistrados": db.execute(
                "SELECT COUNT(*) AS n FROM usuarios"
            ).fetchone()["n"],
            "accesosAutenticados": db.execute(
                "SELECT COUNT(*) AS n FROM accesos_usuarios"
            ).fetchone()["n"],
            "usuariosActivosAutenticados": db.execute(
                "SELECT COUNT(DISTINCT usuario_id) AS n FROM accesos_usuarios"
            ).fetchone()["n"],
            "mensajesNuevos": db.execute(
                "SELECT COUNT(*) AS n FROM mensajes WHERE estado = 'nuevo'"
            ).fetchone()["n"],
            "mensajesTotales": db.execute(
                "SELECT COUNT(*) AS n FROM mensajes"
            ).fetchone()["n"],
            "partidasJugadas": db.execute(
                "SELECT COUNT(*) AS n FROM partidas"
            ).fetchone()["n"],
        }

        registros_por_dia = db.execute(
            f"SELECT date(creado_en) AS dia, COUNT(*) AS altas "
            f"FROM usuarios WHERE {cond_fecha_dt} GROUP BY dia ORDER BY dia",
            params_fecha,
        ).fetchall()

        accesos_por_dia = db.execute(
            f"SELECT fecha AS dia, COUNT(*) AS accesos "
            f"FROM accesos_usuarios WHERE {cond_fecha_vis} "
            f"GROUP BY fecha ORDER BY fecha",
            params_fecha,
        ).fetchall()

        visitas_por_dia = db.execute(
            f"SELECT fecha, contador FROM visitas "
            f"WHERE {cond_fecha_vis} ORDER BY fecha",
            params_fecha,
        ).fetchall()

        if tipo_consulta:
            consultas_por_tipo = db.execute(
                f"SELECT tipo, COUNT(*) AS total FROM mensajes "
                f"WHERE {cond_fecha_dt} AND tipo = ? "
                f"GROUP BY tipo ORDER BY total DESC",
                params_fecha + [tipo_consulta],
            ).fetchall()
        else:
            consultas_por_tipo = db.execute(
                f"SELECT tipo, COUNT(*) AS total FROM mensajes "
                f"WHERE {cond_fecha_dt} GROUP BY tipo ORDER BY total DESC",
                params_fecha,
            ).fetchall()

        # Ahora el filtro de fecha TAMBIÉN aplica al Top Jugadores del dashboard
        if juego:
            top_jugadores = db.execute(
                f"SELECT u.nombre_jugador, ? AS juego, MAX(p.puntaje) AS mejor "
                f"FROM partidas p JOIN usuarios u ON u.id = p.usuario_id "
                f"WHERE {cond_fecha_part} AND p.juego = ? AND p.puntaje > 0 "
                f"GROUP BY u.id ORDER BY mejor DESC LIMIT 5",
                [juego] + params_fecha + [juego],
            ).fetchall()
        else:
            top_jugadores = db.execute(
                f"SELECT u.nombre_jugador, "
                f"(SELECT p2.juego FROM partidas p2 "
                f" WHERE p2.usuario_id = u.id AND "
                f"{cond_fecha_part.replace('p.jugado_en', 'p2.jugado_en')} "
                f" ORDER BY p2.puntaje DESC LIMIT 1) AS juego, "
                f"MAX(p.puntaje) AS mejor "
                f"FROM partidas p JOIN usuarios u ON u.id = p.usuario_id "
                f"WHERE {cond_fecha_part} AND p.puntaje > 0 "
                f"GROUP BY u.id ORDER BY mejor DESC LIMIT 5",
                params_fecha + params_fecha,
            ).fetchall()

        return jsonify({
            "conteos": conteos,
            "registrosPorDia": rows_to_list(registros_por_dia),
            "accesosPorDia": rows_to_list(accesos_por_dia),
            "consultasPorTipo": rows_to_list(consultas_por_tipo),
            "topJugadores": rows_to_list(top_jugadores),
            "visitasPorDia": rows_to_list(visitas_por_dia),
        })

    # ========================================================
    # 8. VISITAS (/api/visitas)
    # ========================================================
    bp_visitas = Blueprint("visitas", __name__, url_prefix="/api/visitas")

    @bp_visitas.post("")
    def registrar_visita():
        db = get_db()
        db.execute(
            "INSERT INTO visitas (fecha, contador) "
            "VALUES (date('now', 'localtime'), 1) "
            "ON CONFLICT(fecha) DO UPDATE SET contador = contador + 1"
        )
        db.commit()
        return jsonify({"ok": True}), 201

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_proyectos)
    app.register_blueprint(bp_servicios)
    app.register_blueprint(bp_mensajes)
    app.register_blueprint(bp_partidas)
    app.register_blueprint(bp_usuarios)
    app.register_blueprint(bp_stats)
    app.register_blueprint(bp_visitas)

    # ========================================================
    # RUTAS DEL FRONTEND Y ARCHIVOS PROTEGIDOS
    # ========================================================
    proto_dir = os.path.join(app.root_path, "prototipo")
    juegos_dir = os.path.join(proto_dir, "juegos")

    @app.get("/")
    @app.get("/index.html")
    def page_index():
        return send_from_directory(proto_dir, "index.html")

    @app.get("/arcade")
    @app.get("/arcade.html")
    def page_arcade():
        return send_from_directory(proto_dir, "arcade.html")

    @app.get("/login")
    @app.get("/registro")
    @app.get("/login.html")
    def page_login():
        return send_from_directory(proto_dir, "login.html")

    @app.get("/maquina.html")
    @app.get("/arcade/<slug>")
    def page_maquina(slug=None):
        if slug:
            return redirect(f"/maquina.html?slug={slug}")
        return send_from_directory(proto_dir, "maquina.html")

    @app.get("/juegos/juego.js")
    def asset_juego_js():
        if not g.usuario:
            return abort(401)
        return send_from_directory(juegos_dir, "juego.js")

    @app.get("/juegos/<path:filename>")
    def page_juego(filename):
        if not g.usuario:
            return redirect(f"/login.html?next=/juegos/{filename}")
        juegos_map = {
            "snake.html": "snake",
            "memory.html": "memory",
            "tateti.html": "ta-te-ti",
        }
        if filename not in juegos_map:
            return abort(404)
        proyecto = get_db().execute('SELECT publicado FROM proyectos WHERE slug = ?',
                                   (juegos_map[filename],)).fetchone()
        if not proyecto or (not proyecto['publicado'] and g.usuario['rol'] != 'admin'):
            return abort(404)
        registrar_acceso(g.usuario["id"], "demo", juegos_map[filename])
        return send_from_directory(juegos_dir, filename)

    @app.get("/admin")
    @app.get("/admin.html")
    def page_admin():
        if not g.usuario:
            return redirect("/login.html?next=/admin.html")
        if g.usuario["rol"] != "admin":
            return redirect("/arcade.html")
        return send_from_directory(proto_dir, "admin.html")

    @app.get("/theme.css")
    def asset_theme_css():
        return send_from_directory(proto_dir, "theme.css")

    @app.get("/arcade.css")
    def asset_arcade_css():
        return send_from_directory(proto_dir, "arcade.css")

    @app.get("/app.js")
    def asset_app_js():
        return send_from_directory(proto_dir, "app.js")

    @app.get('/admin.js')
    def asset_admin_js():
        return send_from_directory(proto_dir, 'admin.js')

    @app.get('/vendor/<path:filename>')
    def asset_vendor(filename):
        return send_from_directory(os.path.join(proto_dir, 'vendor'), filename)

    @app.get('/favicon.ico')
    def favicon():
        return '', 204

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso no encontrado"}), 404
        return redirect("/index.html")

    @app.errorhandler(413)
    def handle_413(e):
        return jsonify({
            "error": "El archivo supera el tamaño máximo permitido (3 MB)"
        }), 413

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"🕹  DevArcade Flask corriendo en http://localhost:{port}")
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=port,
            debug=os.environ.get('FLASK_DEBUG') == '1')
