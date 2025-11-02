# app/blueprints/pago.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Dict, Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json

from flask import (
    Blueprint, current_app, flash, redirect, render_template,
    request, session, url_for
)
import mercadopago

from app.service.qrs import generar_qr
from app.service.pdfs import generar_comprobante_pdf
from app.service.emailer import enviar_ticket
from app.db import get_conn
from app import db as db_mod
from app.data.seed import COMBOS_CATALOG

bp = Blueprint("pago", __name__)

# -------- Helpers MP --------
def _get_mp_token() -> str:
    return (os.getenv("MP_ACCESS_TOKEN") or os.getenv("MERCADOPAGO_ACCESS_TOKEN") or "").strip()

def _sdk_mp():
    token = _get_mp_token()
    if not token:
        current_app.logger.error("Mercado Pago: falta MP_ACCESS_TOKEN/MERCADOPAGO_ACCESS_TOKEN")
        raise RuntimeError("Falta MP_ACCESS_TOKEN en el entorno")
    return mercadopago.SDK(token)

def _mp_token_ok() -> Tuple[bool, str]:
    token = _get_mp_token()
    if not token:
        return False, "Falta MP_ACCESS_TOKEN"
    req = Request(
        "https://api.mercadopago.com/users/me",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=10) as r:
            if r.status == 200:
                return True, ""
            return False, f"users/me devolvió status {r.status}"
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return False, f"{e.code} {e.reason} {body}".strip()
    except URLError as e:
        return False, f"Error de red hacia MP: {e.reason}"
    except Exception as e:
        return False, f"Excepción verificando token: {e}"

# -------- Helpers app --------
def _combos_from_session() -> List[dict]:
    ids = [int(x) for x in session.get("combos", [])]
    idset = set(ids)
    return [c for c in COMBOS_CATALOG if c["id"] in idset]

def _seleccion_from_session() -> dict:
    return session.get("movie_selection", {}) or {}

def _seats_from_session() -> List[str]:
    return session.get("seats", []) or []

def _precio_entrada() -> Decimal:
    raw = str(current_app.config.get("TICKET_PRICE", "5000"))
    try:
        return Decimal(raw)
    except Exception:
        return Decimal("5000")

def _calcular_totales() -> Tuple[Decimal, Decimal, Decimal, list, list, dict]:
    TWO = Decimal("0.01")
    precio = Decimal(str(_precio_entrada()))
    seats = _seats_from_session()
    combos = _combos_from_session()
    seleccion = _seleccion_from_session()

    total_entradas = (precio * Decimal(len(seats))).quantize(TWO, rounding=ROUND_HALF_UP)
    total_combos = sum(
        (Decimal(str(c.get("precio", 0))) for c in combos),
        Decimal("0")
    ).quantize(TWO, rounding=ROUND_HALF_UP)

    total = (total_entradas + total_combos).quantize(TWO, rounding=ROUND_HALF_UP)
    return total_entradas, total_combos, total, combos, seats, seleccion

def _to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

def _is_local(url: str) -> bool:
    # Trata http:// como local (útil en dev)
    return ("127.0.0.1" in url) or ("localhost" in url) or url.startswith("http://")

def _abs_url_for(endpoint: str) -> str:
    rel = url_for(endpoint, _external=False)
    base = (os.getenv("PUBLIC_BASE_URL") or os.getenv("BASE_URL") or request.host_url or "").strip()
    if base and not base.endswith("/"):
        base = base + "/"
    return urljoin(base, rel.lstrip("/"))

def _valid_url(u: str) -> bool:
    return bool(u) and u.startswith(("http://", "https://"))

# -------- Rutas --------
@bp.route("/pago", methods=["GET", "POST"])
def pago():
    # --- Requiere usuario logueado con email ---
    user = session.get("user_autofill") or {}
    user_email = (user.get("email") or "").strip()
    if not user_email:
        flash("Tenés que iniciar sesión para realizar un pago.", "warning")
        # Sugerencia: si tenés un 'next', podrías pasarlo aquí con url_for('auth.login', next=request.path)
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        t_ent, t_combo, total, combos, seats, sel = _calcular_totales()
        if not seats or not sel:
            flash("Primero elegí función y asientos.", "warning")
        return render_template(
            "pago.html",
            errores=None, exito=None, email=user_email,  # email viene de la sesión
            nombre_tarjeta="",
            seleccion=sel, seats=seats, combos=combos,
            monto_sugerido=f"{total:.2f}",
            total_entradas=t_ent, total_combos=t_combo, total=total
        )

    # ---------- POST: crear preferencia ----------
    t_ent, t_combo, total, combos, seats, sel = _calcular_totales()
    if not seats or not sel:
        flash("Primero elegí función y asientos.", "warning")
        return redirect(url_for("pago.pago"))

    # Siempre usar email de la sesión (no pedimos más el campo)
    email = user_email
    session["checkout_email"] = email
    session.modified = True

    # Pre-chequeo de token para mensaje claro si falla
    ok_token, detalle = _mp_token_ok()
    if not ok_token:
        current_app.logger.error("MP token inválido: %s", detalle)
        flash(f"No se pudo iniciar el pago con Mercado Pago: credencial inválida ({detalle})", "danger")
        return redirect(url_for("pago.pago"))

    conn = get_conn()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transacciones (usuario_email, monto_cents, estado, created_at, auth_code)
        VALUES (?,?,?,?,?)
        """,
        (email, _to_cents(total), "INICIADO", now_iso, f"MP-{datetime.now().strftime('%H%M%S')}"),
    )
    trx_id = int(cur.lastrowid or 0)
    conn.commit()
    session["trx_id_mp"] = trx_id
    session.modified = True

    try:
        sdk = _sdk_mp()
    except Exception:
        flash("No se pudo iniciar el pago: error de credenciales de Mercado Pago (ver logs).", "danger")
        return redirect(url_for("pago.pago"))

    success = _abs_url_for("pago.mp_success")
    failure = _abs_url_for("pago.mp_failure")
    pending = _abs_url_for("pago.mp_pending")
    webhook = _abs_url_for("pago.mp_webhook")

    if not (_valid_url(success) and _valid_url(failure) and _valid_url(pending)):
        current_app.logger.error(
            "Back URLs inválidas: success=%s failure=%s pending=%s base=%s host_url=%s",
            success, failure, pending, os.getenv("PUBLIC_BASE_URL"), request.host_url
        )
        flash("No se pudo iniciar el pago: back_urls inválidas (ver logs).", "danger")
        return redirect(url_for("pago.pago"))

    currency = os.getenv("CURRENCY_ID", "ARS")
    pref_data: Dict[str, Any] = {
        "items": [{
            "title": sel.get("titulo", "Entrada de cine"),
            "quantity": 1,
            "currency_id": currency,
            "unit_price": float(total),
        }],
        "payer": {"email": email},
        "back_urls": {"success": success, "failure": failure, "pending": pending},
        "statement_descriptor": "CINEMA3D",
        "metadata": {
            "trx_id": trx_id, "movie_id": sel.get("id"),
            "fecha": sel.get("fecha"), "hora": sel.get("hora"),
            "sala": sel.get("sala"), "seats": ",".join(seats),
        },
        "external_reference": str(trx_id),
    }
    # auto_return solo si success es https (recomendado en producción)
    if success.startswith("https://"):
        pref_data["auto_return"] = "approved"
    # Agregar webhook solo si no estamos en local
    if not _is_local(webhook):
        pref_data["notification_url"] = webhook

    try:
        pref = sdk.preference().create(pref_data)
    except Exception as e:
        current_app.logger.exception("Excepción creando preferencia MP: %s", e)
        flash("No se pudo iniciar el pago con Mercado Pago (excepción en SDK).", "danger")
        return redirect(url_for("pago.pago"))

    status = pref.get("status")
    resp = pref.get("response", {})
    init_point = resp.get("init_point")
    pref_id = resp.get("id")

    if status not in (200, 201) or not init_point:
        current_app.logger.error(
            "Error creando preferencia MP | status=%s | resp=%s | back_urls=%s | public_base=%s | host_url=%s | sent_auto_return=%s",
            status, resp, pref_data.get("back_urls"), os.getenv("PUBLIC_BASE_URL"), request.host_url,
            pref_data.get("auto_return")
        )
        msg = resp.get("message")
        cause = resp.get("cause")
        if cause and isinstance(cause, list) and len(cause) > 0:
            desc = cause[0].get("description")
            if desc:
                msg = f"{msg}: {desc}" if msg else desc
        if not msg and isinstance(resp, dict):
            msg = json.dumps({"status": status, "error": resp.get("error"), "message": resp.get("message")})
        flash(f"No se pudo iniciar el pago con Mercado Pago: {msg or 'ver logs'}", "danger")
        return redirect(url_for("pago.pago"))

    conn.execute(
        "UPDATE transacciones SET estado=?, mp_preference_id=? WHERE id=?",
        ("PENDIENTE", str(pref_id), trx_id),
    )
    conn.commit()
    return redirect(init_point)

@bp.route("/pago/mp/success")
def mp_success():
    trx_id = session.get("trx_id_mp")
    if not trx_id:
        flash("No se pudo asociar el pago a una transacción local.", "warning")
        return redirect(url_for("pago.pago"))

    pid = request.args.get("payment_id") or request.args.get("collection_id")
    if not pid:
        flash("Faltan datos de pago devueltos por Mercado Pago.", "danger")
        return redirect(url_for("pago.pago"))

    sdk = _sdk_mp()
    pay = sdk.payment().get(pid)
    resp = pay.get("response", {})
    if resp.get("status") != "approved":
        _marcar(trx_id, "RECHAZADA")
        flash("El pago no fue aprobado.", "warning")
        return redirect(url_for("pago.mp_failure"))

    t_ent, t_combo, total, combos, seats, sel = _calcular_totales()
    hold_token = session.get("hold_token")
    try:
        confirmados = db_mod.confirm_seats(
            token=hold_token,
            movie_id=sel.get("id"), fecha=sel.get("fecha"),
            hora=sel.get("hora"), sala=sel.get("sala"),
            usuario_email=session.get("checkout_email") or session.get("user_autofill", {}).get("email"),
            trx_id=trx_id,
        )
        if not confirmados:
            _marcar(trx_id, "RECHAZADA")
            flash("Tus asientos ya no estaban retenidos. Volvé a elegirlos.", "warning")
            return redirect(url_for("venta.reserva_asientos"))
    except ValueError as e:
        _marcar(trx_id, "RECHAZADA")
        flash(str(e), "danger")
        return redirect(url_for("venta.reserva_asientos"))

    brand = (resp.get("payment_method", {}) or {}).get("id")
    last4 = (resp.get("card", {}) or {}).get("last_four_digits")
    conn = get_conn()
    conn.execute(
        "UPDATE transacciones SET estado=?, brand=?, last4=?, mp_payment_id=?, fecha_actualizacion=? WHERE id=?",
        ("APROBADO", brand, last4, str(pid), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trx_id),
    )
    conn.commit()

    email = session.get("checkout_email") or session.get("user_autofill", {}).get("email", "")
    sucursal = session.get("branch") or current_app.config.get("DEFAULT_BRANCH", "-")
    auth_code = f"MP-{pid}"
    qr_path = generar_qr(trx_id=trx_id, verify_url=None, extra={"email": email, "auth": auth_code})
    pdf_path = generar_comprobante_pdf(
        trx_id=trx_id, cliente=email or "-", email=email or "-",
        pelicula=sel.get("titulo", "-"),
        fecha_funcion=sel.get("fecha", "-"), hora_funcion=sel.get("hora", "-"),
        sala=sel.get("sala", "-"),
        asientos=confirmados,
        combos=[{"nombre": c["nombre"], "cantidad": 1, "precio": c["precio"]} for c in combos],
        total=float(total), sucursal=sucursal, qr_path=qr_path,
    )

    # -------- ENVÍOS DE EMAIL --------
    # 1) Al CLIENTE (con adjunto PDF)
    try:
        enviar_ticket(
            destino=email,
            asunto=f"Comprobante TRX #{trx_id}",
            cuerpo=(f"Gracias por su compra.\n\nSucursal: {sucursal}\n"
                    f"Película: {sel.get('titulo','-')}\n"
                    f"Fecha/Hora: {sel.get('fecha','-')} {sel.get('hora','-')}\n"
                    f"Asientos: {', '.join(confirmados) if confirmados else '-'}\n"
                    f"Monto: ${total:.2f}\nCódigo de autorización: {auth_code}\n"),
            adjunto_path=pdf_path,
        )
    except Exception as e:
        current_app.logger.warning("Email al cliente no enviado: %s", e)

    # 2) Al CINE (copia interna). Configurá CINEMA_SALES_EMAIL=ventas@tu-cine.com.ar
    sales_email = (os.getenv("CINEMA_SALES_EMAIL") or "").strip()
    if sales_email:
        try:
            enviar_ticket(
                destino=sales_email,
                asunto=f"[Copia interna] TRX #{trx_id} aprobada",
                cuerpo=(f"Se registró una venta aprobada.\n\nCliente: {email or '-'}\n"
                        f"Sucursal: {sucursal}\n"
                        f"Película: {sel.get('titulo','-')}\n"
                        f"Fecha/Hora: {sel.get('fecha','-')} {sel.get('hora','-')}\n"
                        f"Asientos: {', '.join(confirmados) if confirmados else '-'}\n"
                        f"Total: ${total:.2f}\nBrand/Last4: {brand or '-'} • {last4 or '----'}\n"
                        f"Auth: {auth_code}\nTRX local: {trx_id}\n"),
                adjunto_path=pdf_path,  # Podés sacar el adjunto si no querés que llegue al cine
            )
        except Exception as e:
            current_app.logger.warning("Email interno (cine) no enviado: %s", e)

    comprobante_url = url_for("archivos.descargar_comprobante", trx_id=trx_id)

    # Limpieza de sesión
    for k in ("seats", "hold_token", "combos", "trx_id_mp", "checkout_email"):
        session.pop(k, None)
    session.modified = True

    return render_template(
        "pago_ok.html",
        exito="¡Pago aprobado!",
        trx_id=trx_id,
        comprobante_url=comprobante_url,
        seleccion=sel,
        seats=confirmados,
        combos=combos,
        total=float(total),
        brand=brand,
        last4=last4,
        auth_code=auth_code,
    )

@bp.route("/pago/mp/failure")
def mp_failure():
    flash("El pago fue cancelado o rechazado.", "warning")
    return redirect(url_for("pago.pago"))

@bp.route("/pago/mp/pending")
def mp_pending():
    flash("El pago quedó pendiente de acreditación.", "info")
    return redirect(url_for("pago.pago"))

@bp.route("/pago/mp/webhook", methods=["POST"])
def mp_webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        current_app.logger.info("MP webhook: %s", data)
    except Exception as e:
        current_app.logger.warning("Webhook MP sin JSON: %s", e)
    return ("", 200)

def _marcar(trx_id: int, estado: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE transacciones SET estado=?, fecha_actualizacion=? WHERE id=?",
        (estado, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trx_id),
    )
    conn.commit()
