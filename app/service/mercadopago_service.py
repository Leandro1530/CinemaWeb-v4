# app/service/mercadopago_service.py
# -*- coding: utf-8 -*-
"""
Servicio para integración con MercadoPago.
Maneja creación de preferencias, procesamiento de pagos y webhooks.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

import mercadopago
from flask import current_app, url_for

logger = logging.getLogger(__name__)

class MercadoPagoService:
    """Servicio para manejar pagos con MercadoPago"""
    
    def __init__(self):
        self.access_token = os.getenv('MP_ACCESS_TOKEN') or os.getenv('MERCADOPAGO_ACCESS_TOKEN')
        self.public_key = os.getenv('MP_PUBLIC_KEY') or os.getenv('MERCADOPAGO_PUBLIC_KEY')
        
        if not self.access_token:
            raise ValueError("MP_ACCESS_TOKEN no configurado")
        
        # Inicializar SDK
        self.sdk = mercadopago.SDK(self.access_token)
    
    def crear_preferencia_pago(self, 
                              items: List[Dict[str, Any]], 
                              payer_email: str,
                              external_reference: str,
                              metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Crea una preferencia de pago en MercadoPago
        
        Args:
            items: Lista de items a pagar
            payer_email: Email del pagador
            external_reference: Referencia externa (ID de transacción)
            metadata: Metadatos adicionales
        
        Returns:
            Dict con los datos de la preferencia creada
        """
        try:
            # URLs de retorno
            success_url = os.getenv('MP_SUCCESS_URL') or url_for('pago.pago_exitoso', _external=True)
            failure_url = os.getenv('MP_FAILURE_URL') or url_for('pago.pago_fallido', _external=True)
            pending_url = os.getenv('MP_PENDING_URL') or url_for('pago.pago_pendiente', _external=True)
            
            # Calcular total
            total = sum(Decimal(str(item['unit_price'])) * int(item['quantity']) for item in items)
            
            preference_data = {
                "items": items,
                "payer": {
                    "email": payer_email
                },
                "external_reference": external_reference,
                "statement_descriptor": "CINEMA APP",
                "metadata": metadata or {},
                "back_urls": {
                    "success": success_url,
                    "failure": failure_url,
                    "pending": pending_url
                },
                "auto_return": "approved",
                "notification_url": os.getenv('MP_WEBHOOK_URL'),
                "payment_methods": {
                    "excluded_payment_methods": [],
                    "excluded_payment_types": [],
                    "installments": 12  # Hasta 12 cuotas
                },
                "shipments": {
                    "mode": "not_specified"
                }
            }
            
            logger.info(f"Creando preferencia MP para external_reference: {external_reference}")
            
            result = self.sdk.preference().create(preference_data)
            
            if result["status"] == 201:
                preference = result["response"]
                logger.info(f"Preferencia creada exitosamente: {preference['id']}")
                return {
                    "success": True,
                    "preference_id": preference["id"],
                    "init_point": preference["init_point"],
                    "sandbox_init_point": preference.get("sandbox_init_point"),
                    "public_key": self.public_key,
                    "total": float(total)
                }
            else:
                logger.error(f"Error creando preferencia MP: {result}")
                return {
                    "success": False,
                    "error": "Error al crear preferencia de pago",
                    "details": result
                }
                
        except Exception as e:
            logger.error(f"Excepción creando preferencia MP: {str(e)}")
            return {
                "success": False,
                "error": "Error interno al crear preferencia de pago",
                "details": str(e)
            }
    
    def obtener_pago(self, payment_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un pago específico
        
        Args:
            payment_id: ID del pago en MercadoPago
            
        Returns:
            Dict con información del pago
        """
        try:
            result = self.sdk.payment().get(payment_id)
            
            if result["status"] == 200:
                payment = result["response"]
                return {
                    "success": True,
                    "payment": payment,
                    "status": payment["status"],
                    "status_detail": payment["status_detail"],
                    "external_reference": payment.get("external_reference"),
                    "transaction_amount": payment["transaction_amount"],
                    "net_received_amount": payment.get("net_received_amount", 0),
                    "fee_details": payment.get("fee_details", [])
                }
            else:
                logger.error(f"Error obteniendo pago {payment_id}: {result}")
                return {
                    "success": False,
                    "error": "Pago no encontrado",
                    "details": result
                }
                
        except Exception as e:
            logger.error(f"Excepción obteniendo pago {payment_id}: {str(e)}")
            return {
                "success": False,
                "error": "Error interno al obtener pago",
                "details": str(e)
            }
    
    def procesar_webhook(self, webhook_data: Dict) -> Dict[str, Any]:
        """
        Procesa una notificación webhook de MercadoPago
        
        Args:
            webhook_data: Datos del webhook
            
        Returns:
            Dict con resultado del procesamiento
        """
        try:
            action = webhook_data.get("action")
            data_id = webhook_data.get("data", {}).get("id")
            
            if not data_id:
                return {
                    "success": False,
                    "error": "ID de datos no encontrado en webhook"
                }
            
            logger.info(f"Procesando webhook MP - Action: {action}, ID: {data_id}")
            
            if action == "payment.created" or action == "payment.updated":
                # Obtener información del pago
                payment_info = self.obtener_pago(str(data_id))
                
                if payment_info["success"]:
                    return {
                        "success": True,
                        "action": action,
                        "payment_info": payment_info,
                        "should_update_transaction": True
                    }
                else:
                    return payment_info
                    
            else:
                logger.info(f"Acción de webhook no manejada: {action}")
                return {
                    "success": True,
                    "action": action,
                    "should_update_transaction": False,
                    "message": "Acción no requiere procesamiento"
                }
                
        except Exception as e:
            logger.error(f"Excepción procesando webhook MP: {str(e)}")
            return {
                "success": False,
                "error": "Error interno procesando webhook",
                "details": str(e)
            }
    
    def crear_items_desde_carrito(self, entradas: List[Dict], combos: List[Dict]) -> List[Dict[str, Any]]:
        """
        Convierte entradas y combos a formato de items de MercadoPago
        
        Args:
            entradas: Lista de entradas seleccionadas
            combos: Lista de combos seleccionados
            
        Returns:
            Lista de items en formato MercadoPago
        """
        items = []
        
        # Agregar entradas
        for entrada in entradas:
            items.append({
                "id": f"entrada_{entrada['funcion_id']}_{entrada['asiento']}",
                "title": f"Entrada - {entrada.get('pelicula', 'Película')} - Asiento {entrada['asiento']}",
                "description": f"Función: {entrada.get('fecha', '')} {entrada.get('hora', '')}",
                "category_id": "tickets",
                "quantity": 1,
                "unit_price": float(entrada['precio']),
                "currency_id": "ARS"
            })
        
        # Agregar combos
        for combo in combos:
            items.append({
                "id": f"combo_{combo['id']}",
                "title": f"Combo - {combo['nombre']}",
                "description": combo.get('descripcion', ''),
                "category_id": "food",
                "quantity": combo['cantidad'],
                "unit_price": float(combo['precio']),
                "currency_id": "ARS"
            })
        
        return items
    
    def mapear_estado_mp_a_local(self, mp_status: str) -> str:
        """
        Mapea estados de MercadoPago a estados locales
        
        Args:
            mp_status: Estado de MercadoPago
            
        Returns:
            Estado local correspondiente
        """
        mapeo = {
            "approved": "APROBADO",
            "pending": "PENDIENTE", 
            "authorized": "AUTORIZADO",
            "in_process": "PROCESANDO",
            "in_mediation": "MEDIACION",
            "rejected": "RECHAZADO",
            "cancelled": "CANCELADO",
            "refunded": "REEMBOLSADO",
            "charged_back": "CONTRACARGO"
        }
        
        return mapeo.get(mp_status, "DESCONOCIDO")


# Instancia global del servicio
mp_service = MercadoPagoService()