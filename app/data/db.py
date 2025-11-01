# app/db.py
# -*- coding: utf-8 -*-
"""
Capa de acceso a datos (SQLite) para Web_V2.

Incluye:
- conexión por request (g) con row_factory = sqlite3.Row
- helpers query_one/query_all/execute/...
- esquema: usuarios, transacciones
- esquema: seats_holds (retenciones temporales) y seats_reservas (confirmadas)
- helpers de asientos: purge_expired_holds, get_occupied_seats, hold_seats, release_hold

CLI:
    flask init-db
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

import click
from flask import current_app, g

# ----------------------------------------------------------------------
# Conexión y utilidades base
# ----------------------------------------------------------------------

def _db_path() -> str:
    rel = current_app.config.get("DB_PATH", "usuarios.db")
    if not os.path.isabs(rel):
        base = Path(getattr(current_app, "root_path", os.getcwd())).parent
        abs_path = (base / rel).resolve()
    else:
        abs_path = Path(rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return abs_path.as_posix()

def get_conn() -> sqlite3.Connection:
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
        isolation_level=None,  # autocommit-like con "with conn"
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
        """Inicializa (o repara) el esquema de la base de datos SQLite."""
        create_schema()
        click.echo("✔ Base de datos inicializada / verificada.")

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
# Esquema (USUARIOS / TRANSACCIONES + ASIENTOS)
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
--  Tablas de ASIENTOS
-- =========================

-- Retenciones temporales (HOLD).
CREATE TABLE IF NOT EXISTS seats_holds (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id  TEXT    NOT NULL,
    fecha     TEXT    NOT NULL,  -- 'YYYY-MM-DD'
    hora      TEXT    NOT NULL,  -- 'HH:MM'
    sala      TEXT    NOT NULL,
    seat_code TEXT    NOT NULL,  -- ej. 'B5'
    token     TEXT    NOT NULL,  -- identifica la sesión/usuario temporal
    expires_at TEXT   NOT NULL,  -- ISO
    created_at TEXT   NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_holds_show_seat
  ON seats_holds(movie_id, fecha, hora, sala, seat_code);
CREATE INDEX IF NOT EXISTS idx_holds_token     ON seats_holds(token);
CREATE INDEX IF NOT EXISTS idx_holds_expires   ON seats_holds(expires_at);

-- Reservas confirmadas (venta cerrada).
CREATE TABLE IF NOT EXISTS seats_reservas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id  TEXT    NOT NULL,
    fecha     TEXT    NOT NULL,
    hora      TEXT    NOT NULL,
    sala      TEXT    NOT NULL,
    seat_code TEXT    NOT NULL,
    user_id   TEXT,           -- opcional (email u otro id)
    created_at TEXT  NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_res_show_seat
  ON seats_reservas(movie_id, fecha, hora, sala, seat_code);
"""

def create_schema() -> None:
    executescript(SCHEMA_SQL, commit=True)

# ----------------------------------------------------------------------
# Operaciones de dominio (usuarios/transacciones)
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
                (telefono or None), (email or None),
                nro_documento,
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
    row = query_one("SELECT * FROM transacciones WHERE id=?", [trx_id])
    return row_to_dict(row)

def list_transacciones(limit: int = 100, offset: int = 0) -> List[dict]:
    rows = query_all(
        "SELECT * FROM transacciones ORDER BY id DESC LIMIT ? OFFSET ?",
        [int(limit), int(offset)],
    )
    return [row_to_dict(r) for r in rows]

# ----------------------------------------------------------------------
# ASIENTOS: helpers de holds/reservas
# ----------------------------------------------------------------------

def purge_expired_holds() -> int:
    """
    Borra holds vencidos. Devuelve cantidad de filas eliminadas.
    """
    now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    with conn:
        cur = conn.execute("DELETE FROM seats_holds WHERE expires_at < ?", [now_iso])
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
    Devuelve set de asientos ocupados (reservas definitivas + holds activos).
    Si se indica exclude_token, no cuenta los holds de ese token (para que el
    usuario vea sus propios asientos como seleccionables).
    """
    now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    params = [movie_id, fecha, hora, sala]
    holds_sql = """
        SELECT seat_code FROM seats_holds
         WHERE movie_id=? AND fecha=? AND hora=? AND sala=?
           AND expires_at >= ?
    """
    params_h = params + [now_iso]
    if exclude_token:
        holds_sql += " AND token <> ?"
        params_h.append(exclude_token)

    reserva_rows = query_all(
        "SELECT seat_code FROM seats_reservas WHERE movie_id=? AND fecha=? AND hora=? AND sala=?",
        params,
    )
    hold_rows = query_all(holds_sql, params_h)

    occupied = {r["seat_code"] for r in reserva_rows} | {h["seat_code"] for h in hold_rows}
    return occupied

def hold_seats(
    *,
    token: str,
    movie_id: str,
    fecha: str,
    hora: str,
    sala: str,
    seats: list[str],
    ttl_sec: int = 600,
) -> None:
    """
    Crea/actualiza un hold para (token, función) con los asientos indicados.
    - Verifica conflictos con reservas/holds de terceros.
    - Reemplaza el set anterior del mismo token para esa función.
    """
    seats = [s.strip().upper() for s in seats if s and str(s).strip()]
    if not seats:
        return

    # Conflictos
    occupied = get_occupied_seats(
        movie_id=movie_id, fecha=fecha, hora=hora, sala=sala, exclude_token=token
    )
    conflicts = [s for s in seats if s in occupied]
    if conflicts:
        raise ValueError(f"Asientos ocupados: {', '.join(conflicts)}")

    # Upsert del hold (limpiar y volver a insertar)
    expires_iso = (datetime.utcnow() + timedelta(seconds=int(ttl_sec))).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    with conn:
        conn.execute(
            "DELETE FROM seats_holds WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?",
            [token, movie_id, fecha, hora, sala],
        )
        conn.executemany(
            """
            INSERT INTO seats_holds(movie_id, fecha, hora, sala, seat_code, token, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(movie_id, fecha, hora, sala, s, token, expires_iso) for s in seats],
        )

def release_hold(*, token: str, movie_id: str, fecha: str, hora: str, sala: str) -> int:
    """
    Libera el hold de ese token para esa función. Devuelve filas afectadas.
    """
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "DELETE FROM seats_holds WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?",
            [token, movie_id, fecha, hora, sala],
        )
        return int(cur.rowcount or 0)

def confirm_reservation(
    *,
    token: str,
    movie_id: str,
    fecha: str,
    hora: str,
    sala: str,
    user_id: Optional[str] = None,
) -> list[str]:
    """
    (Opcional) Mueve los holds del token a reservas definitivas.
    Devuelve la lista de seats confirmados.
    """
    conn = get_conn()
    with conn:
        rows = query_all(
            "SELECT seat_code FROM seats_holds WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?",
            [token, movie_id, fecha, hora, sala],
        )
        seats = [r["seat_code"] for r in rows]
        if not seats:
            return []

        # Vuelve a chequear conflictos por si algún proceso se adelantó
        occupied = get_occupied_seats(
            movie_id=movie_id, fecha=fecha, hora=hora, sala=sala, exclude_token=token
        )
        for s in seats:
            if s in occupied:
                raise ValueError(f"Asiento {s} ya no está disponible.")

        conn.executemany(
            """
            INSERT OR IGNORE INTO seats_reservas(movie_id, fecha, hora, sala, seat_code, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(movie_id, fecha, hora, sala, s, user_id) for s in seats],
        )
        conn.execute(
            "DELETE FROM seats_holds WHERE token=? AND movie_id=? AND fecha=? AND hora=? AND sala=?",
            [token, movie_id, fecha, hora, sala],
        )
        return seats
