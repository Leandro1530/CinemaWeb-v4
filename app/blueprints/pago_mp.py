# app/blueprints/pago_mp.py
# -*- coding: utf-8 -*-
"""
Blueprint de pago mejorado con integración de MercadoPago.
Mantiene compatibilidad con el sistema de tarjetas existente y agrega MercadoPago como opción.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional

from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
    session,
    url_for,
    redirect,
    jsonify
)

# Imports del sistema existente
from app.service.payments import validar_tarjeta, detectar_brand
from app.service.qrs import generar_qr
from app.service.pdfs import generar_comprobante_pdf
from app.service.emailer import enviar_ticket
from app.db import get_conn, execute, query_one
from app.data.seed import COMBOS_CATALOG

# Nuevo import para MercadoPago
from app.service.mercadopago_service import mp_service

bp = Blueprint("pago_mp", __name__, url_prefix="/pago-mp")
logger = logging.getLogger(__name__)

# ===================== Helpers ===================== #

def _combos_from_session() -> List[dict]:
    """Obtiene los combos seleccionados desde sesión."""
    ids = [int(x) for x in session.get("combos", [])]
    idset = set(ids)
    return [c for c in COMBOS_CATALOG if c["id"] in idset]

def _seleccion_from_session() -> dict:
    """Obtiene la selección de película/función desde sesión."""
    return session.get("movie_selection", {}) or {}

def _seats_from_session() -> List[str]:
    """Obtiene los asientos seleccionados desde sesión."""
    return session.get("seats", []) or []

def _precio_entrada() -> Decimal:
    """Precio unitario de la entrada desde config."""
    raw = str(current_app.config.get("TICKET_PRICE", "2500"))
    try:
        return Decimal(raw)
    except Exception:
        return Decimal("2500")

def _calcular_totales_server_side() -> tuple[Decimal, Decimal, Decimal, list[dict], list[str], dict]:
    """
    Calcula totales en el servidor.
    Returns: (total_entradas, total_combos, total, combos_sel, seats, seleccion)
    """
    TWO = Decimal("0.01")
    precio_ent = _precio_entrada()
    seats = _seats_from_session()
    combos_sel = _combos_from_session()
    seleccion = _seleccion_from_session()

    total_entradas = (precio_ent * Decimal(len(seats))).quantize(TWO, rounding=ROUND_HALF_UP)
    total_combos = sum(Decimal(str(c.get("precio", 0))) for c in combos_sel)
    total_combos = Decimal(total_combos).quantize(TWO, rounding=ROUND_HALF_UP)
    total = (total_entradas + total_combos).quantize(TWO, rounding=ROUND_HALF_UP)

    return total_entradas, total_combos, total, combos_sel, seats, seleccion

def crear_transaccion_pendiente(email: str, total: Decimal, seleccion: dict, 
                              seats: List[str], combos: List[dict]) -> int:
    """
    Crea una transacción en estado PENDIENTE en la base de datos.
    
    Returns:
        int: ID de la transacción creada
    """
    # Generar external_reference único
    external_reference = f"TXN_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    # Preparar datos de asientos y combos
    asientos_data = []
    for seat in seats:
        asientos_data.append({
            "numero": seat,
            "precio": float(_precio_entrada()),
            "funcion_id": seleccion.get("funcion_id"),
            "pelicula": seleccion.get("pelicula", ""),
            "fecha": seleccion.get("fecha", ""),
            "hora": seleccion.get("hora", ""),
            "sala": seleccion.get("sala", "")
        })
    
    combos_data = []
    for combo in combos:
        combos_data.append({
            "id": combo["id"],
            "nombre": combo["nombre"],
            "precio": combo["precio"],
            "cantidad": 1  # Por ahora asumimos cantidad 1
        })
    
    # Insertar en base de datos
    conn = get_conn()
    with conn:
        trans_id = execute(
            """
            INSERT INTO transacciones (
                email_cliente, total_pesos, estado, funcion_id, pelicula,
                fecha_funcion, hora_funcion, sala, asientos_json, combos_json,
                external_reference, ip_cliente, user_agent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                email,
                float(total),
                "PENDIENTE",
                seleccion.get("funcion_id"),
                seleccion.get("pelicula", ""),
                seleccion.get("fecha", ""),
                seleccion.get("hora", ""),
                seleccion.get("sala", ""),
                json.dumps(asientos_data),
                json.dumps(combos_data),
                external_reference,
                request.environ.get('REMOTE_ADDR'),
                request.environ.get('HTTP_USER_AGENT'),
                datetime.now()
            ],
            commit=True
        )
    
    logger.info(f"Transacción PENDIENTE creada: {trans_id} - {external_reference}")
    return trans_id

# ===================== Rutas ===================== #

@bp.route("/", methods=["GET", "POST"])
def procesar_pago():
    """
    Página principal de pago con opciones: MercadoPago o Tarjeta directa
    """
    if request.method == "GET":
        user = session.get("user_autofill", {})
        email = user.get("email", "")
        nombre_tarjeta = f"{user.get('nombre','')} {user.get('apellido','')}".strip().upper()

        total_entradas, total_combos, total, combos, seats, seleccion = _calcular_totales_server_side()

        # Verificar que hay selección válida
        if not seats or not seleccion:
            flash("Primero debes seleccionar función y asientos.", "warning")
            return redirect(url_for('main.inicio'))

        return render_template(
            "pago_mp.html",
            email=email,
            nombre_tarjeta=nombre_tarjeta,
            seleccion=seleccion,
            seats=seats,
            combos=combos,
            total_entradas=total_entradas,
            total_combos=total_combos,
            total=total,
            precio_entrada=_precio_entrada(),
            mp_public_key=mp_service.public_key
        )

    # POST: Procesar según método de pago seleccionado
    metodo_pago = request.form.get("metodo_pago", "mercadopago")
    
    if metodo_pago == "mercadopago":
        return procesar_pago_mercadopago()
    elif metodo_pago == "tarjeta":
        return procesar_pago_tarjeta()
    else:
        flash("Método de pago no válido.", "error")
        return redirect(url_for('pago_mp.procesar_pago'))

def procesar_pago_mercadopago():
    """Procesa el pago usando MercadoPago"""
    try:
        # Validaciones básicas
        email = request.form.get("email", "").strip()
        if not email:
            flash("Email es requerido.", "error")
            return redirect(url_for('pago_mp.procesar_pago'))

        # Calcular totales
        total_entradas, total_combos, total, combos_sel, seats, seleccion = _calcular_totales_server_side()

        if not seats or not seleccion:
            flash("Selección de función y asientos requerida.", "error")
            return redirect(url_for('main.inicio'))

        # Crear transacción pendiente
        trans_id = crear_transaccion_pendiente(email, total, seleccion, seats, combos_sel)
        
        # Crear items para MercadoPago
        items = mp_service.crear_items_desde_carrito(
            entradas=[{
                "funcion_id": seleccion.get("funcion_id"),
                "asiento": seat,
                "precio": float(_precio_entrada()),
                "pelicula": seleccion.get("pelicula", ""),
                "fecha": seleccion.get("fecha", ""),
                "hora": seleccion.get("hora", "")
            } for seat in seats],
            combos=combos_sel
        )

        # Crear preferencia en MercadoPago
        external_reference = query_one(
            "SELECT external_reference FROM transacciones WHERE id = ?", 
            [trans_id]
        )["external_reference"]

        resultado_mp = mp_service.crear_preferencia_pago(
            items=items,
            payer_email=email,
            external_reference=external_reference,
            metadata={
                "transaction_id": trans_id,
                "user_session": session.get("user_id", "anonymous")
            }
        )

        if not resultado_mp["success"]:
            logger.error(f"Error creando preferencia MP: {resultado_mp}")
            flash("Error al procesar el pago. Intenta nuevamente.", "error")
            return redirect(url_for('pago_mp.procesar_pago'))

        # Actualizar transacción con datos de MP
        execute(
            """
            UPDATE transacciones 
            SET mp_preference_id = ?, external_reference = ? 
            WHERE id = ?
            """,
            [resultado_mp["preference_id"], external_reference, trans_id],
            commit=True
        )

        # Guardar en sesión para referencia
        session['pending_transaction_id'] = trans_id
        session['mp_preference_id'] = resultado_mp["preference_id"]

        # Redirigir a MercadoPago
        return redirect(resultado_mp["init_point"])

    except Exception as e:
        logger.error(f"Error procesando pago MP: {str(e)}")
        flash("Error interno procesando el pago.", "error")
        return redirect(url_for('pago_mp.procesar_pago'))

def procesar_pago_tarjeta():
    """Procesa el pago con tarjeta directa (sistema existente)"""
    # Reutilizar la lógica existente del sistema de tarjetas
    total_entradas, total_combos, total, combos_sel, seats, seleccion = _calcular_totales_server_side()

    # Obtener datos del formulario
    email = request.form.get("email", "").strip()
    pan = request.form.get("numero_tarjeta", "").replace(" ", "")
    nombre_tarjeta = request.form.get("nombre_tarjeta", "").strip()
    exp_mes = request.form.get("exp_mes", "")
    exp_anio = request.form.get("exp_anio", "")
    cvv = request.form.get("cvv", "")
    monto_str = f"{total:.2f}"

    # Validar tarjeta
    errores = validar_tarjeta(email, pan, nombre_tarjeta, exp_mes, exp_anio, cvv, monto_str)
    
    if errores:
        return render_template(
            "pago_mp.html",
            errores=errores,
            email=email,
            nombre_tarjeta=nombre_tarjeta.upper(),
            seleccion=seleccion,
            seats=seats,
            combos=combos_sel,
            total_entradas=total_entradas,
            total_combos=total_combos,
            total=total,
            precio_entrada=_precio_entrada(),
            mp_public_key=mp_service.public_key
        )

    # Simular procesamiento de tarjeta (aquí integrarías con tu gateway real)
    brand = detectar_brand(pan)
    last4 = pan[-4:] if len(pan) >= 4 else pan
    auth_code = f"AUTH_{int(datetime.now().timestamp())}"

    # Crear transacción aprobada directamente
    trans_id = crear_transaccion_con_tarjeta(
        email, total, seleccion, seats, combos_sel,
        brand, last4, int(exp_mes), int(exp_anio), auth_code
    )

    # Confirmar asientos y generar comprobante
    from app.blueprints.mercadopago import confirmar_pago_aprobado
    confirmar_pago_aprobado(trans_id, seleccion.get("funcion_id"), 
                          json.dumps([{"numero": seat} for seat in seats]),
                          json.dumps(combos_sel), email)

    # Limpiar sesión
    session.pop("seats", None)
    session.pop("combos", None)
    session.pop("movie_selection", None)

    flash("¡Pago procesado exitosamente!", "success")
    return redirect(url_for('pago_mp.pago_ok', trans_id=trans_id))

def crear_transaccion_con_tarjeta(email: str, total: Decimal, seleccion: dict,
                                seats: List[str], combos: List[dict], brand: str,
                                last4: str, exp_mes: int, exp_anio: int, auth_code: str) -> int:
    """Crea una transacción aprobada con tarjeta"""
    external_reference = f"TXN_CARD_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    asientos_data = []
    for seat in seats:
        asientos_data.append({
            "numero": seat,
            "precio": float(_precio_entrada()),
            "funcion_id": seleccion.get("funcion_id"),
            "pelicula": seleccion.get("pelicula", ""),
            "fecha": seleccion.get("fecha", ""),
            "hora": seleccion.get("hora", ""),
            "sala": seleccion.get("sala", "")
        })
    
    combos_data = []
    for combo in combos:
        combos_data.append({
            "id": combo["id"],
            "nombre": combo["nombre"],
            "precio": combo["precio"],
            "cantidad": 1
        })
    
    conn = get_conn()
    with conn:
        trans_id = execute(
            """
            INSERT INTO transacciones (
                email_cliente, total_pesos, estado, funcion_id, pelicula,
                fecha_funcion, hora_funcion, sala, asientos_json, combos_json,
                external_reference, brand, last4, exp_mes, exp_anio, auth_code,
                ip_cliente, user_agent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                email, float(total), "APROBADO", seleccion.get("funcion_id"),
                seleccion.get("pelicula", ""), seleccion.get("fecha", ""),
                seleccion.get("hora", ""), seleccion.get("sala", ""),
                json.dumps(asientos_data), json.dumps(combos_data),
                external_reference, brand, last4, exp_mes, exp_anio, auth_code,
                request.environ.get('REMOTE_ADDR'),
                request.environ.get('HTTP_USER_AGENT'),
                datetime.now()
            ],
            commit=True
        )
    
    return trans_id

@bp.route("/exito")
@bp.route("/exito/<int:trans_id>")
def pago_ok(trans_id=None):
    """Página de confirmación de pago exitoso"""
    if not trans_id:
        trans_id = session.get('pending_transaction_id')
    
    if not trans_id:
        flash("No se encontró información del pago.", "warning")
        return redirect(url_for('main.inicio'))
    
    # Obtener información de la transacción
    transaccion = query_one(
        "SELECT * FROM transacciones WHERE id = ?", 
        [trans_id]
    )
    
    if not transaccion:
        flash("Transacción no encontrada.", "error")
        return redirect(url_for('main.inicio'))
    
    # Limpiar sesión si el pago está aprobado
    if transaccion["estado"] == "APROBADO":
        session.pop("seats", None)
        session.pop("combos", None)
        session.pop("movie_selection", None)
        session.pop("pending_transaction_id", None)
        session.pop("mp_preference_id", None)
    
    return render_template("pago_ok_mp.html", transaccion=dict(transaccion))

@bp.route("/error")
def pago_error():
    """Página de error de pago"""
    error_data = session.get('mp_failure_data', {})
    return render_template("pago_error.html", error_data=error_data)

@bp.route("/pendiente")
def pago_pendiente():
    """Página de pago pendiente"""
    pending_data = session.get('mp_pending_data', {})
    return render_template("pago_pendiente.html", pending_data=pending_data)

@bp.route("/estado/<int:trans_id>")
def verificar_estado(trans_id: int):
    """API para verificar el estado de una transacción"""
    transaccion = query_one(
        "SELECT id, estado, mp_payment_id, external_reference FROM transacciones WHERE id = ?",
        [trans_id]
    )
    
    if not transaccion:
        return jsonify({"error": "Transacción no encontrada"}), 404
    
    return jsonify({
        "transaction_id": transaccion["id"],
        "status": transaccion["estado"],
        "mp_payment_id": transaccion["mp_payment_id"],
        "external_reference": transaccion["external_reference"]
    })