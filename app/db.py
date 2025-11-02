# app/db.py
# -*- coding: utf-8 -*-
"""
Capa de acceso a datos (SQLite) para Web_V2.

Incluye:
- Conexión por request (g.db) con row_factory = sqlite3.Row
- Helpers query_one/query_all/execute/execute_many/executescript
- Esquema: usuarios, transacciones, seat_holds (retenciones), seat_reservas (definitivas)
- CLI: `flask init-db`
- Funciones de butacas: purge_expired_holds, get_occupied_seats, hold_seats, release_hold, confirm_seats

Compatibilidad con BD antiguas:
- Si ya existen tablas legacy con columnas como `asiento` y sin `seat/token/expires_at`,
  este módulo migra en caliente agregando columnas nuevas y manteniendo la compatibilidad
  (inserta en `seat` y también en `asiento` si ésta existe y es NOT NULL).
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import click
from flask import current_app, g

# ----------------------------------------------------------------------
# Conexión y utilidades base
# ----------------------------------------------------------------------

def _db_path() -> str:
    """Ruta absoluta al archivo SQLite según app.config['DB_PATH'] (o 'usuarios.db')."""
    rel = current_app.config.get("DB_PATH", "usuarios.db")
    if not os.path.isabs(rel):
        base = Path(getattr(current_app, "root_path", os.getcwd())).parent  # /app -> root proyecto
        abs_path = (base / rel).resolve()
    else:
        abs_path = Path(rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return abs_path.as_posix()


def get_conn() -> sqlite3.Connection:
    """Devuelve conexión por request en g.db. Si la existente está cerrada, la reabre."""
    conn = g.get("db")
    if conn is not None:
        try:
            conn.execute("SELECT 1;")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            g.pop("db", None)

    conn = sqlite3.connect(
        _db_path(),
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,  # transacciona con "with conn:"
    )
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;")
    except Exception:
        pass
    g.db = conn
    return conn


def close_conn(_: Optional[BaseException] = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def init_app(app) -> None:
    app.teardown_appcontext(close_conn)

    @app.cli.command("init-db")
    def init_db_command():
        """Inicializa (o migra) el esquema de la base de datos SQLite."""
        create_schema()
        click.echo("✔ Base de datos inicializada / migrada correctamente.")

    @app.cli.command("load-seed")
    def load_seed_command():
        """Carga los datos del archivo seed.py en la base de datos."""
        from app.db_migrations import load_seed_data
        load_seed_data()
        click.echo("✔ Datos semilla cargados correctamente.")


# ----------------------------------------------------------------------
# API de consultas y escritura
# ----------------------------------------------------------------------

def query_one(sql: str, params: Optional[Sequence[Any]] = None) -> Optional[sqlite3.Row]:
    cur = get_conn().execute(sql, params or [])
    row = cur.fetchone()
    cur.close()
    return row


def query_all(sql: str, params: Optional[Sequence[Any]] = None) -> List[sqlite3.Row]:
    cur = get_conn().execute(sql, params or [])
    rows = cur.fetchall()
    cur.close()
    return list(rows)


def execute(sql: str, params: Optional[Sequence[Any]] = None, commit: bool = True) -> int:
    conn = get_conn()
    cur = conn.execute(sql, params or [])
    last_id = cur.lastrowid
    cur.close()
    if commit:
        try:
            conn.commit()
        except Exception:
            pass
    return int(last_id or 0)


def execute_many(sql: str, seq_of_params: Iterable[Sequence[Any]], commit: bool = True) -> int:
    conn = get_conn()
    cur = conn.executemany(sql, list(seq_of_params))
    rowcount = cur.rowcount
    cur.close()
    if commit:
        try:
            conn.commit()
        except Exception:
            pass
    return int(rowcount or 0)


def executescript(script_sql: str, commit: bool = True) -> None:
    conn = get_conn()
    conn.executescript(script_sql)
    if commit:
        try:
            conn.commit()
        except Exception:
            pass


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


# ----------------------------------------------------------------------
# Esquema y bootstrap
# ----------------------------------------------------------------------

SCHEMA_SQL = """
-- =========================
--  Tabla: usuarios
-- =========================
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT    NOT NULL,
    apellido       TEXT    NOT NULL,
    tipo_documento TEXT    NOT NULL,
    nro_documento  TEXT    NOT NULL,
    contrasena     TEXT    NOT NULL, -- hash
    direccion      TEXT,
    ciudad         TEXT,
    provincia      TEXT,
    codigo_postal  TEXT,
    telefono       TEXT,
    email          TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_dni   ON usuarios(nro_documento);
CREATE INDEX        IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- =========================
--  Tabla: transacciones
-- =========================
CREATE TABLE IF NOT EXISTS transacciones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_email TEXT    NOT NULL,
    monto_cents   INTEGER NOT NULL,
    brand         TEXT,
    last4         TEXT,
    exp_mes       INTEGER,
    exp_anio      INTEGER,
    estado        TEXT,
    auth_code     TEXT,
    created_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_trx_email ON transacciones(usuario_email);
CREATE INDEX IF NOT EXISTS idx_trx_fecha ON transacciones(created_at);

-- =========================
--  Tabla moderna: seat_holds
-- =========================
CREATE TABLE IF NOT EXISTS seat_holds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    token      TEXT    NOT NULL DEFAULT '',
    movie_id   TEXT    NOT NULL,
    fecha      TEXT    NOT NULL,
    hora       TEXT    NOT NULL,
    sala       TEXT    NOT NULL,
    seat       TEXT    NOT NULL DEFAULT '',
    expires_at INTEGER NOT NULL DEFAULT 0
);

-- =========================
--  Tabla moderna: seat_reservas
-- =========================
CREATE TABLE IF NOT EXISTS seat_reservas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_email TEXT,
    trx_id        INTEGER,
    movie_id      TEXT    NOT NULL,
    fecha         TEXT    NOT NULL,
    hora          TEXT    NOT NULL,
    sala          TEXT    NOT NULL,
    seat          TEXT    NOT NULL,
    reserved_at   INTEGER NOT NULL
);

-- =========================
--  Tabla: password_reset_tokens
-- =========================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    token      TEXT    NOT NULL,
    expires_at INTEGER NOT NULL,
    used       INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token);
CREATE INDEX        IF NOT EXISTS idx_reset_user  ON password_reset_tokens(user_id);

-- =========================
--  Tabla: funciones
-- =========================
CREATE TABLE IF NOT EXISTS funciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    pelicula_id        TEXT    NOT NULL,
    titulo             TEXT    NOT NULL,
    genero             TEXT,
    duracion           INTEGER,
    clasificacion      TEXT,
    poster             TEXT,
    descripcion        TEXT,
    trailer_url        TEXT,
    fecha              TEXT    NOT NULL,
    hora               TEXT    NOT NULL,
    sala               TEXT    NOT NULL,
    precio             INTEGER DEFAULT 1000,
    asientos_disponibles INTEGER DEFAULT 50,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_funciones_fecha ON funciones(fecha);
CREATE INDEX IF NOT EXISTS idx_funciones_pelicula ON funciones(pelicula_id);
"""


def _table_columns(conn: sqlite3.Connection, table: str) -> List[Tuple[str, bool, Optional[str], bool]]:
    """
    Devuelve lista de columnas: (name, notnull, dflt_value, pk)
    PRAGMA table_info está documentado por SQLite. :contentReference[oaicite:1]{index=1}
    """
    cur = conn.execute(f"PRAGMA table_info({table});")
    cols = [(r["name"], bool(r["notnull"]), r["dflt_value"], bool(r["pk"])) for r in cur.fetchall()]
    cur.close()
    return cols


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(name == column for (name, *_rest) in _table_columns(conn, table))


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """Agrega columna si no existe (con DEFAULT si hace falta por NOT NULL)."""
    if not _has_column(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl};")


def _try_create_index(conn: sqlite3.Connection, create_sql: str, warn: str) -> None:
    try:
        conn.execute(create_sql)
    except sqlite3.OperationalError as e:
        # sucede si columnas no existen en BD legacy o hay duplicados
        current_app.logger.warning("%s: %s", warn, e)


def _migrate_legacy_show_tables(conn: sqlite3.Connection) -> None:
    """
    Migra en caliente `seat_holds` y `seat_reservas` cuando vienen de esquemas viejos:

    - En seat_holds:
        * agrega token TEXT DEFAULT ''
        * agrega seat  TEXT DEFAULT ''
        * agrega expires_at INTEGER DEFAULT 0
        * si existe 'asiento' o 'butaca' y seat está vacío -> copy
        * crea índices tolerantes
    - En seat_reservas:
        * agrega seat TEXT DEFAULT ''
        * si existe 'asiento'/'butaca' y seat vacío -> copy
        * crea índice único moderno si es posible
    """
    # ---- seat_holds ----
    if query_one("SELECT name FROM sqlite_master WHERE type='table' AND name='seat_holds';"):
        with conn:
            _ensure_column(conn, "seat_holds", "token",      "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "seat_holds", "seat",       "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "seat_holds", "expires_at", "INTEGER NOT NULL DEFAULT 0")

            cols = [c[0] for c in _table_columns(conn, "seat_holds")]
            legacy_col = "asiento" if "asiento" in cols else ("butaca" if "butaca" in cols else None)
            if legacy_col:
                # Copiar asiento -> seat cuando seat está vacío o NULL
                conn.execute(
                    f"UPDATE seat_holds SET seat = COALESCE(NULLIF(seat, ''), {legacy_col}) "
                    f"WHERE (seat IS NULL OR seat = '') AND {legacy_col} IS NOT NULL;"
                )

            # Índices (si seat existe, usar seat; si no, intentar con legacy)
            if "seat" in cols:
                _try_create_index(
                    conn,
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_seat_holds_show_seat "
                    "ON seat_holds(movie_id, fecha, hora, sala, seat);",
                    "Índice ux_seat_holds_show_seat",
                )
                _try_create_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS idx_seat_holds_token ON seat_holds(token);",
                    "Índice idx_seat_holds_token",
                )
            elif legacy_col:
                _try_create_index(
                    conn,
                    f"CREATE UNIQUE INDEX IF NOT EXISTS ux_seat_holds_show_legacy "
                    f"ON seat_holds(movie_id, fecha, hora, sala, {legacy_col});",
                    "Índice ux_seat_holds_show_legacy",
                )

    # ---- seat_reservas ----
    if query_one("SELECT name FROM sqlite_master WHERE type='table' AND name='seat_reservas';"):
        with conn:
            _ensure_column(conn, "seat_reservas", "seat", "TEXT NOT NULL DEFAULT ''")
            cols_r = [c[0] for c in _table_columns(conn, "seat_reservas")]
            legacy_r = "asiento" if "asiento" in cols_r else ("butaca" if "butaca" in cols_r else None)
            if legacy_r:
                conn.execute(
                    f"UPDATE seat_reservas SET seat = COALESCE(NULLIF(seat, ''), {legacy_r}) "
                    f"WHERE (seat IS NULL OR seat = '') AND {legacy_r} IS NOT NULL;"
                )
            _try_create_index(
                conn,
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_seat_reservas_show_seat "
                "ON seat_reservas(movie_id, fecha, hora, sala, seat);",
                "Índice ux_seat_reservas_show_seat",
            )
            _try_create_index(
                conn,
                "CREATE INDEX IF NOT EXISTS idx_seat_reservas_trx ON seat_reservas(trx_id);",
                "Índice idx_seat_reservas_trx",
            )


def create_schema() -> None:
    """Crea (o asegura) el esquema moderno y migra tablas legacy en caliente."""
    executescript(SCHEMA_SQL, commit=True)
    conn = get_conn()
    _migrate_legacy_show_tables(conn)


# ----------------------------------------------------------------------
# Operaciones de dominio: usuarios / transacciones
# ----------------------------------------------------------------------

def upsert_usuario(
    *,
    nombre: str,
    apellido: str,
    tipo_documento: str,
    nro_documento: str,
    contrasena_hash: str,
    direccion: Optional[str] = None,
    ciudad: Optional[str] = None,
    provincia: Optional[str] = None,
    codigo_postal: Optional[str] = None,
    telefono: Optional[str] = None,
    email: Optional[str] = None,
) -> int:
    row = query_one("SELECT id FROM usuarios WHERE nro_documento = ?", [nro_documento])
    if row:
        execute(
            """
            UPDATE usuarios
               SET nombre=?, apellido=?, tipo_documento=?, direccion=?,
                   ciudad=?, provincia=?, codigo_postal=?, telefono=?, email=?
             WHERE nro_documento=?
            """,
            [
                nombre, apellido, tipo_documento, (direccion or None),
                (ciudad or None), (provincia or None), (codigo_postal or None),
                (telefono or None), (email or None), nro_documento,
            ],
            commit=True,
        )
        return int(row["id"])

    new_id = execute(
        """
        INSERT INTO usuarios (
            nombre, apellido, tipo_documento, nro_documento, contrasena,
            direccion, ciudad, provincia, codigo_postal, telefono, email
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            nombre, apellido, tipo_documento, nro_documento, contrasena_hash,
            (direccion or None), (ciudad or None), (provincia or None),
            (codigo_postal or None), (telefono or None), (email or None),
        ],
        commit=True,
    )
    return int(new_id)


def insert_transaccion(
    *,
    usuario_email: str,
    monto_cents: int,
    brand: Optional[str] = None,
    last4: Optional[str] = None,
    exp_mes: Optional[int] = None,
    exp_anio: Optional[int] = None,
    estado: Optional[str] = None,
    auth_code: Optional[str] = None,
    created_at: Optional[str] = None,
) -> int:
    trx_id = execute(
        """
        INSERT INTO transacciones (
            usuario_email, monto_cents, brand, last4, exp_mes, exp_anio, estado, auth_code, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            usuario_email, int(monto_cents), (brand or None), (last4 or None),
            (exp_mes if exp_mes is not None else None),
            (exp_anio if exp_anio is not None else None),
            (estado or None), (auth_code or None), (created_at or None),
        ],
        commit=True,
    )
    return int(trx_id)


def get_transaccion(trx_id: int) -> Optional[dict]:
    row = query_one("SELECT * FROM transacciones WHERE id = ?", [trx_id])
    return row_to_dict(row)


def list_transacciones(limit: int = 100, offset: int = 0) -> List[dict]:
    rows = query_all(
        "SELECT * FROM transacciones ORDER BY id DESC LIMIT ? OFFSET ?",
        [int(limit), int(offset)],
    )
    return [row_to_dict(r) for r in rows]


# ----------------------------------------------------------------------
# Utilidades de nombres de columnas (compatibilidad)
# ----------------------------------------------------------------------

def _seat_column_name(conn: sqlite3.Connection, table: str) -> str:
    """Devuelve el nombre de columna a usar para 'asiento': 'seat' o legacy 'asiento'/'butaca'."""
    cols = [c[0] for c in _table_columns(conn, table)]
    if "seat" in cols:
        return "seat"
    if "asiento" in cols:
        return "asiento"
    if "butaca" in cols:
        return "butaca"
    # fallback: creamos 'seat' si nada existe (debería estar por migración)
    _ensure_column(conn, table, "seat", "TEXT NOT NULL DEFAULT ''")
    return "seat"


def _has_notnull_legacy(conn: sqlite3.Connection, table: str) -> bool:
    """¿Existe una columna legacy 'asiento' marcada NOT NULL?"""
    for (name, notnull, _def, _pk) in _table_columns(conn, table):
        if name == "asiento" and notnull:
            return True
    return False


# ----------------------------------------------------------------------
# Operaciones de dominio: asientos
# ----------------------------------------------------------------------

def purge_expired_holds() -> int:
    """Borra holds vencidos (expires_at < ahora)."""
    now = int(time.time())
    conn = get_conn()
    with conn:
        cur = conn.execute("DELETE FROM seat_holds WHERE expires_at < ?", [now])
        return int(cur.rowcount or 0)


def get_occupied_seats(
    *,
    movie_id: str,
    fecha: str,
    hora: str,
    sala: str,
    exclude_token: Optional[str] = None,
) -> set[str]:
    """
    Devuelve los asientos no disponibles (reservados + holds vigentes).
    Si 'exclude_token' está presente, ignora holds de ese token.
    """
    now = int(time.time())
    conn = get_conn()

    # Detectar columnas reales
    seat_col_r = _seat_column_name(conn, "seat_reservas")
    seat_col_h = _seat_column_name(conn, "seat_holds")

    # Reservas definitivas
    cur = conn.execute(
        f"""
        SELECT {seat_col_r} AS s FROM seat_reservas
         WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
        """,
        [movie_id, fecha, hora, sala],
    )
    taken = {row["s"] for row in cur.fetchall()}
    cur.close()

    # Holds vigentes
    if exclude_token and _has_column(conn, "seat_holds", "token"):
        cur = conn.execute(
            f"""
            SELECT {seat_col_h} AS s FROM seat_holds
             WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
               AND expires_at >= ? AND token <> ?
            """,
            [movie_id, fecha, hora, sala, now, exclude_token],
        )
    else:
        cur = conn.execute(
            f"""
            SELECT {seat_col_h} AS s FROM seat_holds
             WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
               AND expires_at >= ?
            """,
            [movie_id, fecha, hora, sala, now],
        )
    held = {row["s"] for row in cur.fetchall()}
    cur.close()

    return taken | held


def hold_seats(
    *,
    token: str,
    movie_id: str,
    fecha: str,
    hora: str,
    sala: str,
    seats: Sequence[str],
    ttl_sec: int,
) -> None:
    """
    Reemplaza el hold del 'token' para la función dada por la lista 'seats'.
    Valida colisiones. Inserta también en la columna legacy `asiento` si existe y es NOT NULL.
    """
    clean_seats = [s.strip().upper() for s in seats if s and str(s).strip()]
    now = int(time.time())
    exp = now + int(ttl_sec)
    conn = get_conn()

    with conn:  # transacción
        # 1) limpiar holds previos de este token para esta función
        if _has_column(conn, "seat_holds", "token"):
            conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [token, movie_id, fecha, hora, sala],
            )
        else:
            # Si no existiera token (muy legacy), limpiamos por función (raro)
            conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [movie_id, fecha, hora, sala],
            )

        if not clean_seats:
            return

        # 2) colisiones con reservas definitivas
        seat_col_r = _seat_column_name(conn, "seat_reservas")
        ph = ",".join("?" for _ in clean_seats)
        cur = conn.execute(
            f"""
            SELECT {seat_col_r} AS s FROM seat_reservas
             WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
               AND {seat_col_r} IN ({ph})
            """,
            [movie_id, fecha, hora, sala, *clean_seats],
        )
        conflicted = [r["s"] for r in cur.fetchall()]
        cur.close()
        if conflicted:
            raise ValueError(f"Asientos ya reservados: {', '.join(conflicted)}")

        # 3) insertar holds respetando columnas presentes
        seat_col_h = _seat_column_name(conn, "seat_holds")
        has_token = _has_column(conn, "seat_holds", "token")
        legacy_notnull = _has_notnull_legacy(conn, "seat_holds")  # 'asiento' NOT NULL?

        for s in clean_seats:
            cols = ["movie_id", "fecha", "hora", "sala", seat_col_h, "expires_at"]
            vals = [movie_id, fecha, hora, sala, s, exp]

            if has_token:
                cols.insert(0, "token")
                vals.insert(0, token)

            # Si la legacy 'asiento' existe y es NOT NULL, asegura rellenarla también
            if legacy_notnull and seat_col_h != "asiento" and _has_column(conn, "seat_holds", "asiento"):
                cols.append("asiento")
                vals.append(s)

            placeholders = ",".join("?" for _ in cols)
            sql = f"INSERT INTO seat_holds ({', '.join(cols)}) VALUES ({placeholders})"
            try:
                conn.execute(sql, vals)
            except sqlite3.IntegrityError as ie:
                # choque con índice único o NOT NULL: reporta asiento ocupado
                raise ValueError(f"Asiento ocupado: {s}") from ie


def release_hold(*, token: str, movie_id: str, fecha: str, hora: str, sala: str) -> int:
    """Libera holds de un token para una función."""
    conn = get_conn()
    with conn:
        if _has_column(conn, "seat_holds", "token"):
            cur = conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [token, movie_id, fecha, hora, sala],
            )
        else:
            cur = conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [movie_id, fecha, hora, sala],
            )
        return int(cur.rowcount or 0)


def confirm_seats(
    *,
    token: str,
    movie_id: str,
    fecha: str,
    hora: str,
    sala: str,
    usuario_email: Optional[str],
    trx_id: Optional[int],
) -> List[str]:
    """
    Convierte los holds del token en reservas definitivas.
    Devuelve la lista de asientos confirmados.
    """
    now = int(time.time())
    conn = get_conn()

    with conn:
        seat_col_h = _seat_column_name(conn, "seat_holds")
        # 1) seats retenidos vigentes por este token
        if _has_column(conn, "seat_holds", "token"):
            cur = conn.execute(
                f"""
                SELECT {seat_col_h} AS s FROM seat_holds
                 WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?
                   AND expires_at >= ?
                """,
                [token, movie_id, fecha, hora, sala, now],
            )
        else:
            cur = conn.execute(
                f"""
                SELECT {seat_col_h} AS s FROM seat_holds
                 WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
                   AND expires_at >= ?
                """,
                [movie_id, fecha, hora, sala, now],
            )
        seats = [r["s"] for r in cur.fetchall()]
        cur.close()
        if not seats:
            return []

        # 2) insertar reservas
        seat_col_r = _seat_column_name(conn, "seat_reservas")
        for s in seats:
            try:
                conn.execute(
                    f"""
                    INSERT INTO seat_reservas
                        (usuario_email, trx_id, movie_id, fecha, hora, sala, {seat_col_r}, reserved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [usuario_email, trx_id, movie_id, fecha, hora, sala, s, now],
                )
            except sqlite3.IntegrityError as ie:
                raise ValueError(f"Asiento ya reservado: {s}") from ie

        # 3) borrar holds consumidos
        if _has_column(conn, "seat_holds", "token"):
            conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [token, movie_id, fecha, hora, sala],
            )
        else:
            conn.execute(
                """
                DELETE FROM seat_holds
                 WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
                """,
                [movie_id, fecha, hora, sala],
            )

    return seats


# =======================================================================
# Password Reset Tokens
# =======================================================================

def create_password_reset_token(user_id: int) -> str:
    """
    Crea un token de recuperación de contraseña para el usuario.
    Elimina tokens anteriores del mismo usuario y genera uno nuevo.
    
    :param user_id: ID del usuario
    :return: token generado
    """
    import secrets
    import time
    
    # Generar token único
    token = secrets.token_urlsafe(32)
    
    # Expiración en 1 hora (3600 segundos)
    expires_at = int(time.time()) + 3600
    
    # Eliminar tokens anteriores del usuario
    execute(
        "DELETE FROM password_reset_tokens WHERE user_id = ?",
        [user_id],
        commit=True
    )
    
    # Crear nuevo token
    execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        [user_id, token, expires_at],
        commit=True
    )
    
    return token


def validate_password_reset_token(token: str) -> Optional[int]:
    """
    Valida un token de recuperación de contraseña.
    
    :param token: token a validar
    :return: user_id si el token es válido, None en caso contrario
    """
    import time
    
    current_time = int(time.time())
    
    # Buscar token válido (no usado y no expirado)
    row = query_one(
        """
        SELECT user_id FROM password_reset_tokens 
        WHERE token = ? AND expires_at > ? AND used = 0
        """,
        [token, current_time]
    )
    
    return row["user_id"] if row else None


def use_password_reset_token(token: str) -> bool:
    """
    Marca un token como usado para que no pueda reutilizarse.
    
    :param token: token a marcar como usado
    :return: True si se marcó correctamente, False si no existe o ya estaba usado
    """
    result = execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE token = ? AND used = 0",
        [token],
        commit=True
    )
    
    return result > 0


def cleanup_expired_reset_tokens() -> None:
    """
    Limpia tokens de recuperación expirados.
    Se puede llamar periódicamente para mantener la tabla limpia.
    """
    import time
    
    current_time = int(time.time())
    
    execute(
        "DELETE FROM password_reset_tokens WHERE expires_at < ?",
        [current_time],
        commit=True
    )
