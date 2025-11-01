# app/blueprints/auth.py
# -*- coding: utf-8 -*-
"""
Blueprint 'auth': registro, login y logout.

Rutas:
- GET  /login
- POST /login
- GET  /logout
- GET  /registro
- POST /registro

Integra con la sesión:
- session["user"] = {id, nombre, apellido, email, nro_documento, rol}
- session["user_autofill"] = {nombre, apellido, email}

Dependencias:
- app/db.py  -> query_one, execute, upsert_usuario
- werkzeug.security -> generate_password_hash, check_password_hash
- Plantillas: templates/login.html, templates/registro.html
"""

from __future__ import annotations

import re
import sqlite3
from typing import Optional, Tuple, Dict, List

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,  # <- para borrar cookies en logout
)

from werkzeug.security import generate_password_hash, check_password_hash

# Usamos el módulo de DB de la app, para tener acceso a sus helpers
from app import db as db_mod

bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_email(value: str) -> bool:
    return bool(value) and EMAIL_RE.match(value.strip().lower()) is not None


def _norm_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    return v or None


def _is_dni_like(value: str) -> bool:
    return bool(value) and re.fullmatch(r"\d{6,12}", value.strip()) is not None


def _safe_next(next_path: Optional[str]) -> Optional[str]:
    """
    Permite solo rutas locales que comiencen con '/'. Evita open redirects.
    """
    if not next_path:
        return None
    next_path = next_path.strip()
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return None


def _find_user_by_login(login_id: str) -> Optional[dict]:
    """
    Busca el usuario por email (case-insensitive) o por nro_documento.
    Devuelve dict con campos relevantes o None.
    """
    if _is_email(login_id):
        row = db_mod.query_one(
            "SELECT id, nombre, apellido, email, nro_documento, contrasena, rol FROM usuarios WHERE lower(email)=lower(?)",
            [login_id.strip().lower()],
        )
    else:
        # asumimos DNI
        row = db_mod.query_one(
            "SELECT id, nombre, apellido, email, nro_documento, contrasena, rol FROM usuarios WHERE nro_documento = ?",
            [login_id.strip()],
        )

    return db_mod.row_to_dict(row)


def _validate_login_form(form) -> Tuple[List[str], str, str]:
    """
    Valida login: login_id + password.
    Retorna: (errores, login_id, password)
    """
    errores: List[str] = []
    login_id = (form.get("login_id") or "").strip()
    password = form.get("password") or ""

    if not login_id:
        errores.append("Ingresá tu email o DNI.")
    if not password:
        errores.append("Ingresá tu contraseña.")

    return errores, login_id, password


def _validate_registro_form(form) -> Tuple[List[str], Dict[str, Optional[str]]]:
    """
    Valida el formulario de registro y devuelve (errores, datos_normalizados).
    No inserta ni actualiza DB; solo valida.
    """
    errores: List[str] = []

    nombre = (form.get("nombre") or "").strip()
    apellido = (form.get("apellido") or "").strip()
    tipo_documento = (form.get("tipo_documento") or "").strip()
    nro_documento = (form.get("nro_documento") or "").strip()
    contrasena = form.get("contrasena") or ""
    email = _norm_email(form.get("email"))
    telefono = (form.get("telefono") or "").strip() or None
    codigo_postal = (form.get("codigo_postal") or "").strip() or None
    direccion = (form.get("direccion") or "").strip() or None
    ciudad = (form.get("ciudad") or "").strip() or None
    provincia = (form.get("provincia") or "").strip() or None

    # Reglas mínimas
    if len(nombre) < 2:
        errores.append("El nombre debe tener al menos 2 caracteres.")
    if len(apellido) < 2:
        errores.append("El apellido debe tener al menos 2 caracteres.")
    if tipo_documento not in {"DNI", "CI", "LE", "LC"}:
        errores.append("Tipo de documento inválido.")
    if not re.fullmatch(r"\d{7,12}", nro_documento):
        errores.append("El número de documento debe ser numérico (7-12 dígitos).")
    if len(contrasena) < 6:
        errores.append("La contraseña debe tener al menos 6 caracteres.")
    if email and not _is_email(email):
        errores.append("Email inválido.")

    # Evitar duplicados obvios (DNI o email ya usados)
    if not errores:
        row = db_mod.query_one(
            "SELECT id FROM usuarios WHERE nro_documento = ?",
            [nro_documento],
        )
        if row:
            errores.append("El documento ya está registrado.")

    if not errores and email:
        row = db_mod.query_one(
            "SELECT id FROM usuarios WHERE lower(email) = lower(?)",
            [email],
        )
        if row:
            errores.append("El email ya está registrado.")

    data = {
        "nombre": nombre,
        "apellido": apellido,
        "tipo_documento": tipo_documento,
        "nro_documento": nro_documento,
        "contrasena": contrasena,
        "email": email,
        "telefono": telefono,
        "codigo_postal": codigo_postal,
        "direccion": direccion,
        "ciudad": ciudad,
        "provincia": provincia,
    }
    return errores, data


def _login_user(user: dict) -> None:
    """
    Rellena la sesión con datos del usuario para uso por el resto de la app.
    """
    session["user"] = {
        "id": user["id"],
        "nombre": user.get("nombre") or "",
        "apellido": user.get("apellido") or "",
        "email": user.get("email"),
        "nro_documento": user.get("nro_documento"),
        "rol": user.get("rol") or "usuario",
    }
    session["user_autofill"] = {
        "nombre": user.get("nombre") or "",
        "apellido": user.get("apellido") or "",
        "email": user.get("email") or "",
    }
    session.permanent = True  # respeta PERMANENT_SESSION_LIFETIME
    session.modified = True


# ---------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login por email o DNI + contraseña.
    Soporta 'next' en querystring/form para redirigir a una ruta local.
    """
    next_url = _safe_next(request.args.get("next")) or _safe_next(request.form.get("next")) or None

    if request.method == "GET":
        # Prefill opcional
        ua = session.get("user_autofill", {})
        return render_template(
            "login.html",
            errores=None,
            login_id=ua.get("email") or ua.get("nro_documento") or "",
            next=next_url,
        )

    # POST
    errores, login_id, password = _validate_login_form(request.form)
    if errores:
        return render_template("login.html", errores=errores, login_id=login_id, next=next_url), 400

    user = _find_user_by_login(login_id)
    if not user:
        return render_template("login.html", errores=["Usuario no encontrado."], login_id=login_id, next=next_url), 400

    if not user.get("contrasena"):
        return render_template("login.html", errores=["Usuario sin contraseña. Contactá al administrador."], login_id=login_id, next=next_url), 400

    if not check_password_hash(user["contrasena"], password):
        return render_template("login.html", errores=["Contraseña incorrecta."], login_id=login_id, next=next_url), 400

    _login_user(user)

    # Redirección final
    if next_url:
        return redirect(next_url)

    # Si está en medio del flujo de compra, vuelve a asientos/confirmación.
    if session.get("seats"):
        return redirect(url_for("venta.confirmacion"))
    if session.get("movie_selection"):
        return redirect(url_for("venta.reserva_asientos"))

    return redirect(url_for("main.bienvenida"))


@bp.get("/logout")
def logout():
    """
    Cierra sesión y limpia datos relevantes (usuario + flujo de compra) y cookies.
    """
    # Claves que queremos asegurarnos de borrar (login + compra)
    for k in (
        "user", "user_autofill", "checkout_email", "seats", "movie_selection",
        "combos", "hold_token", "trx_id_mp"
    ):
        session.pop(k, None)

    # Limpieza total y cookies
    session.clear()
    resp = make_response(redirect(url_for("main.bienvenida")))
    # Borra cookies típicas de sesión/remember (si existieran)
    resp.delete_cookie("session")
    resp.delete_cookie("remember_token")

    flash("Sesión cerrada.", "success")
    return resp


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    """
    Registro de usuario. Inserta nuevo usuario (si el DNI/email no existen).
    Tras registrarse, inicia sesión y redirige según el flujo.
    """
    next_url = _safe_next(request.args.get("next")) or _safe_next(request.form.get("next")) or None

    if request.method == "GET":
        # Mostrar botón "Ir a reserva de asientos" si ya hay selección de función
        mostrar_boton_asientos = bool(session.get("movie_selection"))
        return render_template(
            "registro.html",
            errores=None,
            exito=None,
            mostrar_boton_asientos=mostrar_boton_asientos,
            # Prefill opcional
            nombre="",
            apellido="",
            tipo_documento="DNI",
            nro_documento="",
            email="",
            telefono="",
            codigo_postal="",
            direccion="",
            ciudad="",
            provincia="",
        )

    # POST
    errores, data = _validate_registro_form(request.form)
    if errores:
        return render_template("registro.html", errores=errores, exito=None, **data), 400

    # Hash de contraseña
    pwd_hash = generate_password_hash(data["contrasena"])

    # Insertar (no usamos upsert_usuario para NO sobrescribir contraseñas existentes)
    try:
        user_id = db_mod.execute(
            """
            INSERT INTO usuarios
                (nombre, apellido, tipo_documento, nro_documento, contrasena,
                 direccion, ciudad, provincia, codigo_postal, telefono, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                data["nombre"],
                data["apellido"],
                data["tipo_documento"],
                data["nro_documento"],
                pwd_hash,
                data["direccion"],
                data["ciudad"],
                data["provincia"],
                data["codigo_postal"],
                data["telefono"],
                data["email"],
            ],
            commit=True,
        )
    except sqlite3.IntegrityError:
        # Índice único en nro_documento/email
        return render_template(
            "registro.html",
            errores=["El documento o el email ya están registrados."],
            exito=None,
            **data,
        ), 400

    # Autologin
    user = {
        "id": user_id,
        "nombre": data["nombre"],
        "apellido": data["apellido"],
        "email": data["email"],
        "nro_documento": data["nro_documento"],
        "rol": "usuario",
    }
    _login_user(user)

    # Mensaje y redirección
    flash("¡Registro exitoso! Bienvenido/a.", "success")

    if next_url:
        return redirect(next_url)

    if session.get("movie_selection"):
        # Si estaba en el flujo de compra, continúe a seleccionar asientos o confirmación
        if session.get("seats"):
            return redirect(url_for("venta.confirmacion"))
        return redirect(url_for("venta.reserva_asientos"))

    return redirect(url_for("main.bienvenida"))


# =======================================================================
# Funciones de autorización y verificación de admin
# =======================================================================

def current_user():
    """Retorna los datos del usuario actual desde la sesión"""
    return session.get("user")


def is_logged_in():
    """Verifica si hay un usuario logueado"""
    return current_user() is not None


def is_admin():
    """Verifica si el usuario actual es administrador"""
    user = current_user()
    return user and user.get("rol") == "admin"


def require_login():
    """Decorador que requiere que el usuario esté logueado"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                return redirect(url_for('auth.login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin():
    """Decorador que requiere que el usuario sea administrador"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                return redirect(url_for('auth.login', next=request.url))
            if not is_admin():
                flash("No tienes permisos para acceder a esta sección.", "error")
                return redirect(url_for('main.bienvenida'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
