# app/blueprints/venta.py
# -*- coding: utf-8 -*-
"""
Blueprint 'venta': flujo de compra previa al pago.

Rutas:
- GET  /cartelera                 -> Lista de películas y funciones
- POST /seleccionar-funcion       -> Guarda función elegida en sesión
- GET/POST /reserva-asientos      -> Selección y hold de asientos
- GET/POST /combos                -> Selección de combos
- GET  /confirmacion              -> Resumen previo al pago

Requisitos:
- app/data/seed.py -> MOVIES, COMBOS_CATALOG
- templates/cartelera.html
- templates/reserva_asientos.html
- templates/combos.html (opcional)
- templates/confirmacion.html
- app/db.py con helpers:
    - purge_expired_holds()
    - get_occupied_seats(movie_id, fecha, hora, sala, exclude_token=None) -> set[str]
    - hold_seats(token, movie_id, fecha, hora, sala, seats, ttl_sec)
    - release_hold(token, movie_id, fecha, hora, sala) (opcional)
"""

from __future__ import annotations

import os
import uuid
import importlib
from typing import Iterable

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.data.seed import MOVIES, COMBOS_CATALOG
import app.db as db_mod

bp = Blueprint("venta", __name__)


# =========================
# Utilitarios internos
# =========================

def _get_branch() -> str:
    """Sucursal actual (desde sesión o config)."""
    return session.get("branch") or current_app.config.get("DEFAULT_BRANCH", "Sucursal")


def _rows_cols_from_config() -> tuple[list[str], int, int]:
    """
    Devuelve (rows_str_list, cols, max_per_order).
    - SEAT_ROWS: string con letras de fila, ej. "ABCDEFGHIJ"
    - SEAT_COLS: cantidad de columnas (int)
    - SEAT_MAX_PER_ORDER: máximo de butacas por compra
    """
    rows_str = list(str(current_app.config.get("SEAT_ROWS", "ABCDEFGHIJ")))
    cols = int(current_app.config.get("SEAT_COLS", 12))
    max_per = int(current_app.config.get("SEAT_MAX_PER_ORDER", 6))
    return rows_str, cols, max_per


def _movies_source() -> list[dict]:
    """
    Fuente de catálogo:
    - Consulta la base de datos de funciones para obtener películas dinámicamente.
    """
    def safe_get(row, key, default=None):
        """Helper para obtener valores de sqlite3.Row con default"""
        try:
            return row[key] if row[key] is not None else default
        except (KeyError, IndexError):
            return default
    
    try:
        # Obtener todas las funciones desde la base de datos
        funciones_db = db_mod.query_all("""
            SELECT DISTINCT pelicula_id, titulo, genero, duracion, clasificacion,
                   poster, descripcion
            FROM funciones
            ORDER BY titulo
        """)
        
        movies = []
        for pelicula in funciones_db:
            # Obtener todas las funciones de esta película
            funciones_pelicula = db_mod.query_all("""
                SELECT fecha, hora, sala, precio, asientos_disponibles
                FROM funciones
                WHERE pelicula_id = ?
                ORDER BY fecha, hora
            """, [pelicula['pelicula_id']])
            
            # Formatear las funciones
            funciones_formateadas = []
            for funcion in funciones_pelicula:
                funciones_formateadas.append({
                    'fecha': safe_get(funcion, 'fecha'),
                    'hora': safe_get(funcion, 'hora'),
                    'sala': safe_get(funcion, 'sala', 'Sala 1'),
                    'precio': safe_get(funcion, 'precio', 100),
                    'asientos_disponibles': safe_get(funcion, 'asientos_disponibles', 50)
                })
            
            # Construir el objeto película compatible con el formato original
            movies.append({
                'id': pelicula['pelicula_id'],
                'titulo': pelicula['titulo'],
                'poster_url': safe_get(pelicula, 'poster', ''),
                'sinopsis': safe_get(pelicula, 'descripcion', ''),
                'duracion_min': safe_get(pelicula, 'duracion', 120),
                'clasificacion': safe_get(pelicula, 'clasificacion', '+13'),
                'genero': safe_get(pelicula, 'genero', 'Acción'),
                'funciones': funciones_formateadas
            })
        
        return movies
    except Exception as e:
        current_app.logger.error(f"Error al cargar películas desde BD: {e}")
        # Fallback a MOVIES hardcodeado en caso de error
        return current_app.config.get("DEMO_MOVIES") or MOVIES or []


def _normalize_seats(value: str | Iterable[str]) -> list[str]:
    """Normaliza asientos a lista de códigos 'A1', 'B3', ... en mayúsculas."""
    if isinstance(value, str):
        parts = [s.strip().upper() for s in value.split(",") if s.strip()]
        return parts
    return [str(s).strip().upper() for s in value if str(s).strip()]


def _selection_from_form_or_session() -> dict:
    """
    Obtiene la selección de función:
    - Primero intenta desde el form (compatibilidad con distintas plantillas).
    - Si no hay, usa session["movie_selection"] si existe.
    """
    movie_id = (request.form.get("movie_id") or "").strip()
    titulo = (request.form.get("titulo") or "").strip()
    sala = (request.form.get("sala") or "").strip()
    fecha = (request.form.get("fecha") or "").strip()
    hora = (request.form.get("hora") or "").strip()

    if movie_id and sala and fecha and hora:
        return {
            "id": movie_id,
            "titulo": titulo,
            "sala": sala,
            "fecha": fecha,
            "hora": hora,
        }

    sel = session.get("movie_selection")
    return sel or {}


def _ensure_hold_token() -> str:
    """Asegura un token por sesión para retener asientos (hold)."""
    tok = session.get("hold_token")
    if not tok:
        tok = uuid.uuid4().hex
        session["hold_token"] = tok
        session.modified = True
    return tok


def _ensure_db_symbols() -> None:
    """
    Defensa ante recargas calientes: si por alguna razón el módulo quedó
    parcialmente inicializado, recárgalo para garantizar símbolos.
    """
    global db_mod  # noqa: PLW0603
    if not hasattr(db_mod, "get_occupied_seats") or not hasattr(db_mod, "hold_seats"):
        db_mod = importlib.reload(db_mod)


# =========================
# Rutas
# =========================

@bp.get("/cartelera")
def cartelera():
    """Lista de películas disponibles para la sucursal actual."""
    sucursal = _get_branch()
    movies = _movies_source()
    current_app.logger.info(
        "Cartelera: %s películas para sucursal=%s", len(movies), sucursal
    )
    return render_template("cartelera.html", movies=movies, sucursal=sucursal)


@bp.post("/seleccionar-funcion")
def seleccionar_funcion():
    """
    Guarda en sesión la función seleccionada y redirige a /reserva-asientos.
    Acepta dos variantes:
    - (movie_id, funcion_idx)
    - (movie_id, titulo, sala, fecha, hora)
    """
    # Variante por índice (usada por tarjetas con múltiples funciones)
    movie_id = (request.form.get("movie_id") or "").strip()
    funcion_idx = request.form.get("funcion_idx")

    if funcion_idx is not None:
        try:
            idx = int(funcion_idx)
        except (TypeError, ValueError):
            flash("Función inválida", "danger")
            return redirect(url_for("venta.cartelera"))

        movie = next((m for m in _movies_source() if m.get("id") == movie_id), None)
        if not movie:
            flash("Película no encontrada", "danger")
            return redirect(url_for("venta.cartelera"))

        try:
            f = movie["funciones"][idx]
        except Exception:
            flash("Función inválida", "danger")
            return redirect(url_for("venta.cartelera"))

        session["movie_selection"] = {
            "id": movie["id"],
            "titulo": movie.get("titulo", ""),
            "sala": f.get("sala", ""),
            "fecha": f.get("fecha", ""),
            "hora": f.get("hora", ""),
        }
        session.modified = True
        session.pop("seats", None)  # limpiar asientos previos
        return redirect(url_for("venta.reserva_asientos"))

    # Variante por campos sueltos
    sel = _selection_from_form_or_session()
    if not sel:
        flash("Debés seleccionar una función", "danger")
        return redirect(url_for("venta.cartelera"))

    session["movie_selection"] = sel
    session.modified = True
    session.pop("seats", None)
    return redirect(url_for("venta.reserva_asientos"))


@bp.route("/reserva-asientos", methods=["GET", "POST"])
def reserva_asientos():
    """
    GET: Renderiza mapa de asientos con ocupados/seleccionados.
    POST: Valida y retiene (hold) los asientos elegidos; redirige a /combos.
    """
    _ensure_db_symbols()

    sel = session.get("movie_selection")
    if not sel:
        flash("Primero elegí una función.", "warning")
        return redirect(url_for("venta.cartelera"))

    rows_str, cols, max_per = _rows_cols_from_config()
    hold_token = _ensure_hold_token()

    # Limpieza de holds vencidos (no es crítico si falla)
    try:
        removed = db_mod.purge_expired_holds()
        if removed:
            current_app.logger.debug("Holds vencidos purgados: %s", removed)
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning("No se pudo purgar holds vencidos: %s", e)

    # Ocupados (reservas definitivas + holds de otros)
    reserved_set = db_mod.get_occupied_seats(
        movie_id=sel.get("id"),
        fecha=sel.get("fecha"),
        hora=sel.get("hora"),
        sala=sel.get("sala"),
        exclude_token=hold_token,  # mis propios holds no bloquean
    )

    if request.method == "GET":
        # Precio de entrada desde configuración
        precio_entrada = float(current_app.config.get("TICKET_PRICE", "5000"))
        
        return render_template(
            "reserva_asientos.html",
            pelicula=sel.get("titulo"),
            fecha=sel.get("fecha"),
            hora=sel.get("hora"),
            sala=sel.get("sala"),
            rows_str=rows_str,
            cols=cols,
            max_per_order=max_per,
            reserved=reserved_set,
            selected=session.get("seats", []),
            precio_entrada=precio_entrada,
        )

    # --- POST: procesar selección --- #
    seats_raw = request.form.get("seats", "")
    selected = _normalize_seats(seats_raw)

    if not selected:
        flash("Seleccioná al menos un asiento.", "warning")
        return redirect(url_for("venta.reserva_asientos"))

    if len(selected) > max_per:
        flash(f"No podés seleccionar más de {max_per} asientos.", "danger")
        return redirect(url_for("venta.reserva_asientos"))

    still_occupied = [s for s in selected if s in reserved_set]
    if still_occupied:
        flash(
            f"Los asientos {', '.join(still_occupied)} acaban de ocuparse. Elegí otros.",
            "danger",
        )
        return redirect(url_for("venta.reserva_asientos"))

    ttl = int(os.getenv("HOLD_TTL_SECONDS", "600"))  # 10 minutos por defecto
    try:
        db_mod.hold_seats(
            token=hold_token,
            movie_id=sel.get("id"),
            fecha=sel.get("fecha"),
            hora=sel.get("hora"),
            sala=sel.get("sala"),
            seats=selected,
            ttl_sec=ttl,
        )
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Error al crear hold de asientos: %s", e)
        flash("No se pudieron retener los asientos. Probá de nuevo.", "danger")
        return redirect(url_for("venta.reserva_asientos"))

    session["seats"] = selected
    session.modified = True
    return redirect(url_for("venta.combos"))


@bp.route("/combos", methods=["GET", "POST"])
def combos():
    """
    Selección de combos. Guarda en sesión 'combos' como lista de IDs (int).
    """
    sel = session.get("movie_selection")
    seats = session.get("seats") or []
    if not sel or not seats:
        flash("Elegí la función y los asientos primero.", "warning")
        return redirect(url_for("venta.cartelera"))

    if request.method == "GET":
        # Mostrar página de combos
        return render_template("combos.html", combos=COMBOS_CATALOG)

    # POST
    ids = request.form.getlist("combos") or request.form.getlist("combo_id")
    sel_ids: list[int] = []
    for x in ids:
        try:
            sel_ids.append(int(x))
        except Exception:  # noqa: BLE001
            continue

    session["combos"] = sel_ids
    session.modified = True
    return redirect(url_for("venta.confirmacion"))


@bp.get("/confirmacion")
def confirmacion():
    """
    Resumen previo al pago. Muestra lo elegido y botón para ir a /pago.
    """
    sel = session.get("movie_selection")
    seats = session.get("seats") or []
    if not sel or not seats:
        flash("Falta elegir función y asientos.", "warning")
        return redirect(url_for("venta.cartelera"))

    # Combos elegidos a partir de los IDs en sesión
    ids = [int(x) for x in session.get("combos", [])]
    idset = set(ids)
    combos_elegidos = [c for c in COMBOS_CATALOG if c["id"] in idset]

    # Totales
    # Si no definiste un precio por entrada, queda en 0.
    precio_entrada = float(current_app.config.get("TICKET_PRICE", 0))
    total_entradas = precio_entrada * len(seats)
    total_combos = sum(float(c.get("precio", 0) or 0) for c in combos_elegidos)
    total = total_entradas + total_combos

    return render_template(
        "confirmacion.html",
        seleccion=sel,                       # dict con {id, titulo, sala, fecha, hora}
        seats=seats,                         # lista de asientos seleccionados
        combos=combos_elegidos,              # lista de combos elegidos
        total_entradas=total_entradas,       # para que puedas mostrarlo si querés
        total_combos=total_combos,           # idem
        total=total,                         # <— esto resuelve el error en la plantilla
        sucursal=session.get("branch") or current_app.config.get("DEFAULT_BRANCH"),
    )
