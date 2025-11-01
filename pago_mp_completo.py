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

bp = Blueprint("pago_mp", __name__, url_prefix="/pago")
logger = logging.getLogger(__name__)

# ===================== Helpers ===================== #

def _combos_from_session() -> List[dict]:
    """Obtiene los combos seleccionados desde sesión."""
    ids = [int(x) for x in session.get("combos", [])]
    idset = set(ids)
    return [c for c in COMBOS_CATALOG if c["id"] in idset]

def _calcular_totales_server_side():
    """Calcula totales del lado del servidor para validación."""
    combos = _combos_from_session()
    seats = session.get("seats", [])
    seleccion = session.get("seleccion", {})
    
    if not seats or not seleccion:
        return 0, 0, 0, [], [], {}
    
    # Calcular entradas
    precio_entrada = Decimal(str(seleccion.get("precio", 0)))
    total_entradas = len(seats) * precio_entrada
    
    # Calcular combos
    total_combos = sum(Decimal(str(combo["precio"])) for combo in combos)
    
    # Total
    total = total_entradas + total_combos
    
    return total_entradas, total_combos, total, combos, seats, seleccion

def crear_transaccion_pendiente(email: str, total: Decimal, seleccion: dict, seats: list, combos: list) -> int:
    """Crea una transacción pendiente en la base de datos."""
    trans_id = execute("""
        INSERT INTO transacciones (
            email, monto_total, estado, 
            pelicula, fecha_funcion, hora_funcion, sala,
            asientos, combos, fecha_creacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        email,
        float(total),
        "PENDIENTE",
        seleccion.get("titulo", ""),
        seleccion.get("fecha", ""),
        seleccion.get("hora", ""),
        seleccion.get("sala", ""),
        json.dumps(seats),
        json.dumps([{"id": c["id"], "nombre": c["nombre"], "precio": c["precio"]} for c in combos]),
        datetime.now().isoformat()
    ])
    return trans_id

def actualizar_transaccion_aprobada(trans_id: int, metodo_pago: str, referencia_externa: Optional[str] = None):
    """Actualiza una transacción como aprobada."""
    execute("""
        UPDATE transacciones 
        SET estado = ?, metodo_pago = ?, referencia_externa = ?, fecha_aprobacion = ?
        WHERE id = ?
    """, ["APROBADO", metodo_pago, referencia_externa, datetime.now().isoformat(), trans_id])

# ===================== Rutas ===================== #

@bp.route("/")
def procesar_pago():
    """Página principal de pago con opciones MercadoPago y tarjeta."""
    try:
        # Validar datos de usuario desde la sesión
        user = session.get("user", {})
        if not user or not user.get("email"):
            flash("Debes completar tus datos primero.", "warning")
            return redirect(url_for('main.inicio'))

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
            total_formatted=f"{float(total):.2f}"
        )

    except Exception as e:
        logger.error(f"Error en procesar_pago: {e}")
        flash("Error al cargar la página de pago.", "error")
        return redirect(url_for('venta.cartelera'))

@bp.route("/procesar", methods=["POST"])
def procesar_pago_post():
    """Procesa el pago según el método seleccionado."""
    try:
        metodo_pago = request.form.get("metodo_pago")
        email = request.form.get("email", "").strip()

        if not email:
            flash("Email requerido.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

        # Actualizar email en sesión
        user = session.get("user", {})
        user["email"] = email
        session["user"] = user

        total_entradas, total_combos, total, combos_sel, seats, seleccion = _calcular_totales_server_side()

        if not seats or not seleccion:
            flash("Selección de función y asientos requerida.", "error")
            return redirect(url_for('main.inicio'))

        # Crear transacción pendiente
        trans_id = crear_transaccion_pendiente(email, total, seleccion, seats, combos_sel)
        
        # Guardar ID de transacción en sesión
        session["pending_transaction_id"] = trans_id

        if metodo_pago == "mercadopago":
            return procesar_mercadopago(trans_id, email, total, seleccion, seats, combos_sel)
        elif metodo_pago == "tarjeta":
            return procesar_tarjeta(trans_id, email, total, seleccion, seats, combos_sel)
        else:
            flash("Método de pago no válido.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

    except Exception as e:
        logger.error(f"Error en procesar_pago_post: {e}")
        flash("Error al procesar el pago.", "error")
        return redirect(url_for("pago_mp.procesar_pago"))

def procesar_mercadopago(trans_id: int, email: str, total: Decimal, seleccion: dict, seats: list, combos: list):
    """Procesa pago con MercadoPago."""
    try:
        # Crear preferencia de MercadoPago
        items = []
        
        # Agregar entradas
        if seats:
            items.append({
                "title": f"{seleccion.get('titulo', 'Película')} - {len(seats)} entrada(s)",
                "quantity": len(seats),
                "unit_price": float(seleccion.get("precio", 0)),
                "currency_id": "ARS"
            })
        
        # Agregar combos
        for combo in combos:
            items.append({
                "title": combo["nombre"],
                "quantity": 1,
                "unit_price": float(combo["precio"]),
                "currency_id": "ARS"
            })

        preference_data = {
            "items": items,
            "payer": {
                "email": email
            },
            "back_urls": {
                "success": url_for("pago_mp.pago_exitoso", trans_id=trans_id, _external=True),
                "failure": url_for("pago_mp.pago_fallido", trans_id=trans_id, _external=True),
                "pending": url_for("pago_mp.pago_pendiente", trans_id=trans_id, _external=True)
            },
            "auto_return": "approved",
            "external_reference": str(trans_id),
            "notification_url": url_for("mercadopago.webhook", _external=True)
        }

        # Crear preferencia usando el servicio
        preference = mp_service.crear_preferencia(preference_data)
        
        if preference and "init_point" in preference:
            # Guardar preference_id en la transacción
            execute("""
                UPDATE transacciones 
                SET preference_id = ? 
                WHERE id = ?
            """, [preference["id"], trans_id])
            
            # Redirigir a MercadoPago
            return redirect(preference["init_point"])
        else:
            logger.error(f"Error creando preferencia MP para transacción {trans_id}")
            flash("Error al inicializar MercadoPago. Intenta con tarjeta.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

    except Exception as e:
        logger.error(f"Error en procesar_mercadopago: {e}")
        flash("Error con MercadoPago. Intenta con tarjeta.", "error")
        return redirect(url_for("pago_mp.procesar_pago"))

def procesar_tarjeta(trans_id: int, email: str, total: Decimal, seleccion: dict, seats: list, combos: list):
    """Procesa pago con tarjeta (sistema existente)."""
    try:
        # Obtener datos de tarjeta del formulario
        numero_tarjeta = request.form.get("numero_tarjeta", "").replace(" ", "")
        mes_exp = request.form.get("mes_exp", "")
        anio_exp = request.form.get("anio_exp", "")
        cvv = request.form.get("cvv", "")
        nombre_tarjeta = request.form.get("nombre_tarjeta", "").strip().upper()

        # Validar campos
        if not all([numero_tarjeta, mes_exp, anio_exp, cvv, nombre_tarjeta]):
            flash("Todos los campos de la tarjeta son obligatorios.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

        # Validar tarjeta
        if not validar_tarjeta(numero_tarjeta, mes_exp, anio_exp, cvv):
            flash("Datos de tarjeta inválidos.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

        # Simular procesamiento exitoso (reemplazar con gateway real)
        success = True  # Aquí iría la lógica real de procesamiento

        if success:
            # Marcar transacción como aprobada
            actualizar_transaccion_aprobada(trans_id, "TARJETA", f"CARD_{numero_tarjeta[-4:]}")
            
            # Procesar compra exitosa
            return finalizar_compra_exitosa(trans_id)
        else:
            flash("Error al procesar la tarjeta. Intenta nuevamente.", "error")
            return redirect(url_for("pago_mp.procesar_pago"))

    except Exception as e:
        logger.error(f"Error en procesar_tarjeta: {e}")
        flash("Error al procesar la tarjeta.", "error")
        return redirect(url_for("pago_mp.procesar_pago"))

def finalizar_compra_exitosa(trans_id: int):
    """Finaliza una compra exitosa generando tickets y limpiando sesión."""
    try:
        # Obtener transacción
        transaccion = query_one("SELECT * FROM transacciones WHERE id = ?", [trans_id])
        
        if not transaccion:
            flash("Transacción no encontrada.", "error")
            return redirect(url_for('main.inicio'))

        # Generar QR
        qr_path = generar_qr(trans_id)
        
        # Generar PDF
        pdf_path = generar_comprobante_pdf(transaccion, qr_path)
        
        # Enviar email
        enviar_ticket(transaccion["email"], pdf_path)
        
        # Limpiar sesión
        session.pop("seats", None)
        session.pop("seleccion", None)
        session.pop("combos", None)
        session.pop("pending_transaction_id", None)
        
        # Mostrar página de éxito
        flash("¡Pago procesado exitosamente! Revisa tu email.", "success")
        return render_template("pago_ok.html", transaccion=transaccion)

    except Exception as e:
        logger.error(f"Error en finalizar_compra_exitosa: {e}")
        flash("Pago procesado pero error al generar ticket.", "warning")
        return redirect(url_for('main.inicio'))

@bp.route("/exito/<int:trans_id>")
def pago_exitoso(trans_id: int):
    """Callback de éxito de MercadoPago."""
    try:
        # Verificar que la transacción existe y está pendiente
        transaccion = query_one("SELECT * FROM transacciones WHERE id = ? AND estado = 'PENDIENTE'", [trans_id])
        
        if not transaccion:
            flash("Transacción no válida.", "error")
            return redirect(url_for('main.inicio'))

        # Obtener información del pago desde MercadoPago
        payment_id = request.args.get("payment_id")
        
        if payment_id:
            # Verificar el estado del pago con MercadoPago
            payment_info = mp_service.obtener_pago(payment_id)
            
            if payment_info and payment_info.get("status") == "approved":
                # Marcar como aprobado
                actualizar_transaccion_aprobada(trans_id, "MERCADOPAGO", payment_id)
                
                # Finalizar compra
                return finalizar_compra_exitosa(trans_id)
        
        # Si llegamos aquí, el pago no está confirmado
        flash("Pago pendiente de confirmación.", "info")
        return redirect(url_for("pago_mp.estado_pago", trans_id=trans_id))

    except Exception as e:
        logger.error(f"Error en pago_exitoso: {e}")
        flash("Error al procesar el éxito del pago.", "error")
        return redirect(url_for('main.inicio'))

@bp.route("/fallido/<int:trans_id>")
def pago_fallido(trans_id: int):
    """Callback de fallo de MercadoPago."""
    flash("El pago fue cancelado o falló. Puedes intentar nuevamente.", "error")
    return redirect(url_for("pago_mp.procesar_pago"))

@bp.route("/pendiente/<int:trans_id>")
def pago_pendiente(trans_id: int):
    """Callback de pago pendiente de MercadoPago."""
    flash("Tu pago está siendo procesado. Te notificaremos cuando se confirme.", "info")
    return redirect(url_for("pago_mp.estado_pago", trans_id=trans_id))

@bp.route("/estado/<int:trans_id>")
def estado_pago(trans_id: int):
    """Muestra el estado actual de un pago."""
    try:
        # Obtener desde parámetro URL o sesión
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
            session.pop("seleccion", None)
            session.pop("combos", None)
            session.pop("pending_transaction_id", None)

        return render_template("estado_pago.html", transaccion=transaccion)

    except Exception as e:
        logger.error(f"Error en estado_pago: {e}")
        flash("Error al obtener estado del pago.", "error")
        return redirect(url_for('main.inicio'))

# ===================== API Endpoints ===================== #

@bp.route("/api/estado/<int:trans_id>")
def api_estado_pago(trans_id: int):
    """API para verificar estado de pago (para polling desde frontend)."""
    try:
        transaccion = query_one("SELECT estado, metodo_pago, fecha_aprobacion FROM transacciones WHERE id = ?", [trans_id])
        
        if not transaccion:
            return jsonify({"error": "Transacción no encontrada"}), 404
        
        return jsonify({
            "estado": transaccion["estado"],
            "metodo_pago": transaccion["metodo_pago"],
            "fecha_aprobacion": transaccion["fecha_aprobacion"]
        })

    except Exception as e:
        logger.error(f"Error en api_estado_pago: {e}")
        return jsonify({"error": "Error interno"}), 500