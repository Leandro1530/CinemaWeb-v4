# app/service/emailer.py
# -*- coding: utf-8 -*-
"""
Servicio de email:
- Usa Flask-Mail para enviar sin exponer AUTH en consola.
- Si EMAIL_DEBUG=1, NO envía; sólo registra un mensaje informativo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from flask import current_app
from flask_mail import Message

from app.extensions import mail


def enviar_ticket(
    *,
    destino: str,
    asunto: str,
    cuerpo: str,
    adjunto_path: Optional[str] = None,
) -> None:
    """
    Envía un email (o lo simula si EMAIL_DEBUG=1).

    :param destino: email destino
    :param asunto: asunto del correo
    :param cuerpo: cuerpo en texto plano
    :param adjunto_path: ruta a PDF (opcional)
    """
    cfg = current_app.config
    if cfg.get("EMAIL_DEBUG", True):
        # NO enviamos nada en modo debug: sólo logueamos una línea clara.
        current_app.logger.info(
            "EMAIL_DEBUG=1: no se envía correo. destino=%s adjunto=%s",
            destino,
            adjunto_path or "-",
        )
        return

    # Compose message
    msg = Message(
        subject=asunto,
        recipients=[destino],
        body=cuerpo,
    )

    # Adjuntar PDF si existe
    if adjunto_path:
        try:
            p = Path(adjunto_path)
            if p.exists() and p.is_file():
                with p.open("rb") as f:
                    data = f.read()
                msg.attach(
                    filename=p.name,
                    content_type="application/pdf",
                    data=data,
                )
            else:
                current_app.logger.warning("Adjunto no encontrado: %s", adjunto_path)
        except Exception as e:
            current_app.logger.warning("No se pudo adjuntar %s: %s", adjunto_path, e)

    # Enviar con Flask-Mail
    try:
        mail.send(msg)
        current_app.logger.info("Email enviado a %s (asunto=%s)", destino, asunto)
    except Exception as e:
        # No exponemos credenciales ni el intercambio SMTP
        current_app.logger.error("Error enviando email a %s: %s", destino, e)
        # No relanzamos; dejamos que el flujo de compra continúe.
