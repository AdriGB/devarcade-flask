-- ============================================================
-- DevArcade — db/schema.sql
-- Corrige FK en respuestas(admin_id): permite ON DELETE SET NULL
-- y conserva admin_nombre histórico para no bloquear borrado de admins.
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_jugador TEXT NOT NULL UNIQUE,
  email          TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  rol            TEXT NOT NULL DEFAULT 'user' CHECK (rol IN ('user','admin')),
  activo         INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
  creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS proyectos (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo       TEXT NOT NULL,
  slug         TEXT NOT NULL UNIQUE,
  descripcion  TEXT NOT NULL,
  tecnologias  TEXT,
  imagen       TEXT,
  demo_url     TEXT,
  tipo         TEXT NOT NULL DEFAULT 'demo' CHECK (tipo IN ('proyecto','demo')),
  orden        INTEGER NOT NULL DEFAULT 0,
  destacado    INTEGER NOT NULL DEFAULT 0 CHECK (destacado IN (0, 1)),
  publicado    INTEGER NOT NULL DEFAULT 1 CHECK (publicado IN (0, 1)),
  creado_en    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS servicios (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo          TEXT NOT NULL UNIQUE,
  descripcion     TEXT NOT NULL,
  icono           TEXT,
  precio_estimado TEXT,
  activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
  creado_en       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS mensajes (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre    TEXT NOT NULL,
  email     TEXT NOT NULL,
  asunto    TEXT,
  tipo      TEXT NOT NULL DEFAULT 'consulta'
            CHECK (tipo IN ('consulta','cotizacion','asesoria')),
  mensaje   TEXT NOT NULL,
  estado    TEXT NOT NULL DEFAULT 'nuevo'
            CHECK (estado IN ('nuevo','respondido','error_envio')),
  creado_en TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS respuestas (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  mensaje_id    INTEGER NOT NULL REFERENCES mensajes(id) ON DELETE CASCADE,
  admin_id      INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
  admin_nombre  TEXT NOT NULL DEFAULT 'admin',
  cuerpo        TEXT NOT NULL,
  modo_envio    TEXT NOT NULL DEFAULT 'simulado'
                CHECK (modo_envio IN ('smtp','simulado','fallido')),
  detalle_envio TEXT,
  enviado_en    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS partidas (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  juego       TEXT NOT NULL,
  resultado_id TEXT,
  puntaje     INTEGER NOT NULL CHECK (puntaje >= 0 AND puntaje <= 1000000),
  jugado_en   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS visitas (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha    TEXT NOT NULL UNIQUE DEFAULT (date('now','localtime')),
  contador INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accesos_usuarios (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  evento     TEXT NOT NULL DEFAULT 'login'
             CHECK (evento IN ('login','registro','demo')),
  recurso    TEXT,
  fecha      TEXT NOT NULL DEFAULT (date('now','localtime')),
  creado_en  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_partidas_usuario ON partidas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_partidas_juego   ON partidas(juego);
CREATE UNIQUE INDEX IF NOT EXISTS idx_partida_resultado ON partidas(usuario_id, resultado_id);
CREATE INDEX IF NOT EXISTS idx_mensajes_estado  ON mensajes(estado);
CREATE INDEX IF NOT EXISTS idx_accesos_fecha    ON accesos_usuarios(fecha);
CREATE INDEX IF NOT EXISTS idx_accesos_usuario  ON accesos_usuarios(usuario_id);
