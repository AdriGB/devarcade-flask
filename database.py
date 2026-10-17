import os
import sqlite3
from flask import g, current_app


def get_db():
    if "db" not in g:
        db_path = current_app.config["DB_PATH"]
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(app):
    schema_path = os.path.join(app.root_path, "db", "schema.sql")
    with app.app_context():
        db = get_db()
        with open(schema_path, "r", encoding="utf-8") as f:
            db.executescript(f.read())

        cols_u = [
            r["name"]
            for r in db.execute("PRAGMA table_info(usuarios)").fetchall()
        ]
        if "activo" not in cols_u:
            db.execute(
                "ALTER TABLE usuarios "
                "ADD COLUMN activo INTEGER NOT NULL DEFAULT 1;"
            )

        cols_p = [
            r["name"]
            for r in db.execute("PRAGMA table_info(proyectos)").fetchall()
        ]
        if "demo_url" not in cols_p:
            db.execute("ALTER TABLE proyectos ADD COLUMN demo_url TEXT;")

        cols_r = [
            r["name"]
            for r in db.execute("PRAGMA table_info(respuestas)").fetchall()
        ]
        if "admin_nombre" not in cols_r:
            db.execute(
                "ALTER TABLE respuestas "
                "ADD COLUMN admin_nombre TEXT NOT NULL DEFAULT 'admin';"
            )
        db.commit()


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]
