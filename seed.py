"""Datos mínimos de demostración. Ejecutar varias veces no duplica registros."""
from werkzeug.security import generate_password_hash
from app import create_app
from database import get_db


def run_seed(app=None):
    app = app or create_app()
    with app.app_context():
        db = get_db()
        for nombre, email, password, rol in [
            ("admin", "admin@devarcade.dev", "admin1234", "admin"),
            ("pixel_lucia", "lucia@mail.com", "jugadora1", "user"),
        ]:
            if not db.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone():
                db.execute("INSERT INTO usuarios (nombre_jugador,email,password_hash,rol) VALUES (?,?,?,?)",
                           (nombre, email, generate_password_hash(password), rol))
        for orden, (titulo, slug, descripcion, tec, ruta) in enumerate([
            ("Snake", "snake", "Comé manzanas, evitá las paredes y superá tu récord. Incluye controles táctiles y pausa.", "JavaScript, Canvas, Flask, SQLite", "/juegos/snake.html"),
            ("Memory", "memory", "Encontrá las ocho parejas con pocos movimientos y en el menor tiempo posible.", "JavaScript, DOM, CSS Grid, Flask", "/juegos/memory.html"),
            ("Ta-Te-Ti", "ta-te-ti", "Desafiá a la computadora en nivel fácil o imposible, con algoritmo minimax.", "JavaScript, Minimax, Flask, SQLite", "/juegos/tateti.html"),
        ], 1):
            db.execute("""INSERT INTO proyectos (titulo,slug,descripcion,tecnologias,demo_url,tipo,orden,destacado)
                       VALUES (?,?,?,?,?,'demo',?,1) ON CONFLICT(slug) DO NOTHING""",
                       (titulo, slug, descripcion, tec, ruta, orden))
        for titulo, desc, icono in [
            ("Desarrollo web fullstack", "Interfaces adaptables, backend en Python y bases de datos relacionales.", "💻"),
            ("Landing pages y portfolios", "Sitios con identidad visual propia y navegación adaptada a celulares.", "🎨"),
            ("APIs y automatización", "Integraciones y scripts para simplificar tareas repetitivas.", "⚙️"),
        ]:
            db.execute("INSERT INTO servicios (titulo,descripcion,icono) VALUES (?,?,?) ON CONFLICT(titulo) DO NOTHING",
                       (titulo, desc, icono))
        db.commit()
    print("Base lista. Admin: admin@devarcade.dev / admin1234")
    print("Jugador: lucia@mail.com / jugadora1")


if __name__ == "__main__":
    run_seed()
