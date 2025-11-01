# app/blueprints/mercadopago.py
# -*- coding: utf-8 -*-
"""
Blueprint para manejar webhooks y callbacks de MercadoPago
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, flash, redirect, url_for, session

from app.service.mercadopago_service import mp_service
from app.db import get_conn
from app.service.emailer import enviar_ticket
from app.service.pdfs import generar_comprobante_pdf
from app.service.qrs import generar_qr

bp = Blueprint("mercadopago", __name__, url_prefix="/webhook")
logger = logging.getLogger(__name__)

@bp.route("/mercadopago", methods=["POST"])
def webhook_mercadopago():
    """
    Endpoint para recibir notificaciones de MercadoPago
    """
    try:
        # Obtener datos del webhook
        webhook_data = request.get_json()
        
        if not webhook_data:
            logger.warning("Webhook MP recibido sin datos JSON")
            return jsonify({"status": "error", "message": "No data"}), 400
        
        logger.info(f"Webhook MP recibido: {json.dumps(webhook_data, indent=2)}")
        
        # Procesar webhook
        result = mp_service.procesar_webhook(webhook_data)
        
        if not result["success"]:
            logger.error(f"Error procesando webhook MP: {result}")
            return jsonify({"status": "error", "message": result["error"]}), 400
        
        # Si el webhook requiere actualizar la transacción
        if result.get("should_update_transaction", False):
            payment_info = result["payment_info"]
            external_reference = payment_info["payment"].get("external_reference")
            
            if external_reference:
                actualizar_resultado = actualizar_transaccion_desde_mp(
                    external_reference, 
                    payment_info
                )
                
                if actualizar_resultado["success"]:
                    logger.info(f"Transacción {external_reference} actualizada desde webhook MP")
                else:
                    logger.error(f"Error actualizando transacción {external_reference}: {actualizar_resultado}")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Excepción en webhook MP: {str(e)}")
        return jsonify({"status": "error", "message": "Internal error"}), 500

def actualizar_transaccion_desde_mp(external_reference: str, payment_info: dict) -> dict:
    """
    Actualiza una transacción local basada en información de MercadoPago
    
    Args:
        external_reference: Referencia externa (ID de transacción local)
        payment_info: Información del pago de MercadoPago
    
    Returns:
        Dict con resultado de la actualización
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Obtener información del pago
        payment = payment_info["payment"]
        mp_payment_id = payment["id"]
        mp_status = payment["status"]
        mp_status_detail = payment["status_detail"]
        transaction_amount = payment["transaction_amount"]
        net_amount = payment.get("net_received_amount", 0)
        
        # Mapear estado de MP a estado local
        estado_local = mp_service.mapear_estado_mp_a_local(mp_status)
        
        # Buscar la transacción local
        cursor.execute("""
            SELECT id, estado, email_cliente, total_pesos, funcion_id, asientos_json, combos_json
            FROM transacciones 
            WHERE id = %s OR external_reference = %s
        """, (external_reference, external_reference))
        
        transaccion = cursor.fetchone()
        
        if not transaccion:
            logger.warning(f"Transacción no encontrada: {external_reference}")
            return {
                "success": False,
                "error": "Transacción no encontrada"
            }
        
        trans_id, estado_actual, email_cliente, total_local, funcion_id, asientos_json, combos_json = transaccion
        
        # Solo actualizar si hay cambio de estado
        if estado_actual == estado_local:
            logger.info(f"Transacción {external_reference} ya tiene estado {estado_local}")
            return {
                "success": True,
                "message": "Estado ya actualizado",
                "no_change": True
            }
        
        # Actualizar transacción
        cursor.execute("""
            UPDATE transacciones 
            SET estado = %s, 
                mp_payment_id = %s,
                mp_status = %s,
                mp_status_detail = %s,
                monto_mp = %s,
                monto_neto_mp = %s,
                fecha_actualizacion = %s
            WHERE id = %s
        """, (
            estado_local, 
            mp_payment_id, 
            mp_status, 
            mp_status_detail,
            transaction_amount,
            net_amount,
            datetime.now(),
            trans_id
        ))
        
        # Si el pago fue aprobado, confirmar asientos y generar comprobante
        if estado_local == "APROBADO" and estado_actual != "APROBADO":
            resultado_confirmacion = confirmar_pago_aprobado(
                trans_id, 
                funcion_id, 
                asientos_json, 
                combos_json,
                email_cliente
            )
            
            if not resultado_confirmacion["success"]:
                logger.error(f"Error confirmando pago {trans_id}: {resultado_confirmacion}")
                # No hacer rollback, mantener el estado MP pero marcar error
                cursor.execute("""
                    UPDATE transacciones 
                    SET notas = %s 
                    WHERE id = %s
                """, (f"Error confirmando: {resultado_confirmacion['error']}", trans_id))
        
        conn.commit()
        
        logger.info(f"Transacción {external_reference} actualizada: {estado_actual} -> {estado_local}")
        
        return {
            "success": True,
            "transaction_id": trans_id,
            "old_status": estado_actual,
            "new_status": estado_local,
            "mp_payment_id": mp_payment_id
        }
        
    except Exception as e:
        logger.error(f"Error actualizando transacción {external_reference}: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if 'conn' in locals():
            conn.close()

def confirmar_pago_aprobado(trans_id: int, funcion_id: int, asientos_json: str, 
                          combos_json: str, email_cliente: str) -> dict:
    """
    Confirma un pago aprobado: confirma asientos, genera QR y PDF, envía email
    
    Args:
        trans_id: ID de la transacción
        funcion_id: ID de la función
        asientos_json: JSON con asientos seleccionados
        combos_json: JSON con combos seleccionados  
        email_cliente: Email del cliente
    
    Returns:
        Dict con resultado de la confirmación
    """
    try:
        import json
        from app.db import confirm_seats
        
        # Parsear asientos y combos
        asientos = json.loads(asientos_json) if asientos_json else []
        combos = json.loads(combos_json) if combos_json else []
        
        # Confirmar asientos (convertir holds a reservas definitivas)
        if asientos:
            asientos_nums = [asiento["numero"] for asiento in asientos]
            confirm_result = confirm_seats(funcion_id, asientos_nums)
            
            if not confirm_result.get("success", True):
                return {
                    "success": False,
                    "error": f"Error confirmando asientos: {confirm_result.get('error', 'Unknown')}"
                }
        
        # Generar QR
        qr_path = None
        try:
            qr_path = generar_qr(trans_id)
        except Exception as e:
            logger.warning(f"Error generando QR para transacción {trans_id}: {str(e)}")
        
        # Generar PDF del comprobante
        pdf_path = None
        try:
            pdf_path = generar_comprobante_pdf(trans_id)
        except Exception as e:
            logger.warning(f"Error generando PDF para transacción {trans_id}: {str(e)}")
        
        # Enviar email de confirmación
        try:
            if email_cliente and pdf_path:
                enviar_ticket(email_cliente, trans_id, pdf_path)
        except Exception as e:
            logger.warning(f"Error enviando email para transacción {trans_id}: {str(e)}")
        
        return {
            "success": True,
            "qr_path": qr_path,
            "pdf_path": pdf_path,
            "email_sent": bool(email_cliente and pdf_path)
        }
        
    except Exception as e:
        logger.error(f"Error confirmando pago aprobado {trans_id}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@bp.route("/success")
def pago_exitoso():
    """Página de éxito después del pago en MercadoPago"""
    collection_id = request.args.get('collection_id')
    collection_status = request.args.get('collection_status')
    payment_id = request.args.get('payment_id')
    status = request.args.get('status')
    external_reference = request.args.get('external_reference')
    payment_type = request.args.get('payment_type')
    merchant_order_id = request.args.get('merchant_order_id')
    preference_id = request.args.get('preference_id')
    site_id = request.args.get('site_id')
    processing_mode = request.args.get('processing_mode')
    merchant_account_id = request.args.get('merchant_account_id')
    
    logger.info(f"Callback éxito MP - payment_id: {payment_id}, status: {status}, external_reference: {external_reference}")
    
    # Guardar información en la sesión para mostrar en el template
    session['mp_success_data'] = {
        'payment_id': payment_id,
        'status': status,
        'external_reference': external_reference,
        'collection_status': collection_status
    }
    
    # Si tenemos external_reference, verificar el estado del pago
    if external_reference and payment_id:
        try:
            payment_info = mp_service.obtener_pago(payment_id)
            if payment_info["success"]:
                actualizar_transaccion_desde_mp(external_reference, payment_info)
        except Exception as e:
            logger.error(f"Error verificando pago en callback de éxito: {str(e)}")
    
    flash("¡Pago procesado exitosamente! Recibirás un email con tu comprobante.", "success")
    return redirect(url_for('pago_mp.pago_ok'))

@bp.route("/failure")
def pago_fallido():
    """Página de fallo después del pago en MercadoPago"""
    payment_id = request.args.get('payment_id')
    status = request.args.get('status')
    external_reference = request.args.get('external_reference')
    
    logger.info(f"Callback fallo MP - payment_id: {payment_id}, status: {status}, external_reference: {external_reference}")
    
    # Guardar información en la sesión
    session['mp_failure_data'] = {
        'payment_id': payment_id,
        'status': status,
        'external_reference': external_reference
    }
    
    flash("El pago no pudo ser procesado. Puedes intentar nuevamente.", "error")
    return redirect(url_for('pago_mp.pago_error'))

@bp.route("/pending")
def pago_pendiente():
    """Página de pago pendiente"""
    payment_id = request.args.get('payment_id')
    status = request.args.get('status')
    external_reference = request.args.get('external_reference')
    
    logger.info(f"Callback pendiente MP - payment_id: {payment_id}, status: {status}, external_reference: {external_reference}")
    
    session['mp_pending_data'] = {
        'payment_id': payment_id,
        'status': status,
        'external_reference': external_reference
    }
    
    flash("Tu pago está siendo procesado. Te notificaremos cuando esté confirmado.", "info")
    return redirect(url_for('pago_mp.pago_pendiente'))