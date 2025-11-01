# app/mp_routes.py
import os, json
from flask import Blueprint, request, jsonify, redirect
import mercadopago

mp_bp = Blueprint("mp_bp", __name__, url_prefix="/mp")

ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
PUBLIC_KEY   = os.getenv("MP_PUBLIC_KEY")
BASE_URL     = os.getenv("BASE_URL", "http://127.0.0.1:5000")

if not ACCESS_TOKEN:
    raise RuntimeError("Falta MP_ACCESS_TOKEN en el entorno")

sdk = mercadopago.SDK(ACCESS_TOKEN)

@mp_bp.route("/checkout", methods=["POST"])
def mp_checkout():
    data = request.get_json(silent=True) or {}
    # Datos mínimos (cámbialos según tu carrito/entrada)
    title       = data.get("title", "Entrada de cine")
    quantity    = int(data.get("quantity", 1))
    unit_price  = float(data.get("unit_price", 5000.0))
    currency_id = data.get("currency_id", "ARS")
    payer_email = data.get("email")  # opcional

    preference_data = {
        "items": [{
            "title": title,
            "quantity": quantity,
            "currency_id": currency_id,
            "unit_price": unit_price
        }],
        "payer": {"email": payer_email} if payer_email else {},
        "back_urls": {
            "success": f"{BASE_URL}/mp/success",
            "failure": f"{BASE_URL}/mp/failure",
            "pending": f"{BASE_URL}/mp/pending",
        },
        "auto_return": "approved",
        "notification_url": f"{BASE_URL}/mp/webhook"
    }

    pref = sdk.preference().create(preference_data)
    # En producción se usa "init_point"
    init_point = pref["response"].get("init_point")
    if not init_point:
        return jsonify({"ok": False, "error": "No se pudo crear la preferencia", "mp": pref}), 500

    # Devolvemos la URL para redirigir desde el front
    return jsonify({"ok": True, "init_point": init_point})

@mp_bp.route("/success")
def mp_success():
    # Mercado Pago vuelve con query params: collection_id, payment_id, status, etc.
    # Podés leerlos, guardar en DB y mostrar un ticket/OK.
    return "Pago aprobado. ¡Gracias!"

@mp_bp.route("/failure")
def mp_failure():
    return "Pago fallido o cancelado."

@mp_bp.route("/pending")
def mp_pending():
    return "Pago pendiente de acreditación."

@mp_bp.route("/webhook", methods=["POST"])
def mp_webhook():
    # Recibís eventos de pago. Guardá/logueá y confirmá con 200.
    # Si querés validar firma, agregá manejo de headers X-Signature (opcional mínimo).
    try:
        body = request.get_json(force=True)
        # TODO: procesar evento (payment approved, etc.)
        # print(json.dumps(body, indent=2, ensure_ascii=False))
    except Exception:
        body = {"raw": request.data.decode("utf-8", "ignore")}
    return ("", 200)
