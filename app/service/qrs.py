# cinema/services/qrs.py
# -*- coding: utf-8 -*-
"""
Generación y almacenamiento de códigos QR para tickets/entradas.

Dependencias:
  - qrcode[pil]  (provee qrcode y Pillow)
  - Flask (solo para current_app)

Uso típico (desde un blueprint/servicio):
    from cinema.services.qrs import generar_qr

    qr_path = generar_qr(
        trx_id=trx_id,
        verify_url=f"https://mi-dominio.example/validar/{trx_id}",
        extra={"pelicula": pelicula_titulo, "email": email},
        # opcionales:
        # filename=f"qr_trx_{trx_id}.png",
        # logo_path="static/img/logo.png",
        # error_correction="M", box_size=8, border=3,
    )
"""
from __future__ import annotations

import os
import json
import hmac
import base64
import hashlib
from datetime import datetime
from typing import Any, Mapping, Optional

from flask import current_app

import qrcode
from qrcode.constants import (
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
    ERROR_CORRECT_H,
)

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # Logo opcional, no obligatorio


__all__ = ["generar_qr", "QRGenerationError"]


class QRGenerationError(Exception):
    """Error al generar o guardar el código QR."""


# ========= helpers internos ========= #

def _ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _abs_storage_dir(rel_or_abs: str) -> str:
    """Convierte un path relativo (a la raíz Flask) en absoluto."""
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    base = getattr(current_app, "root_path", os.getcwd())
    return os.path.join(base, rel_or_abs)


def _map_ec(level: str):
    level = (level or "M").upper()
    return {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }.get(level, ERROR_CORRECT_M)


def _sign_payload(payload: str, secret: str) -> str:
    """Devuelve firma HMAC-SHA256 en base64-url-safe (sin =)"""
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def _build_payload(
    *,
    trx_id: int,
    verify_url: Optional[str],
    extra: Optional[Mapping[str, Any]],
) -> str:
    """
    Construye un payload JSON compacto. Si existe QR_SIGN_SECRET en config,
    agrega firma HMAC en 'sig'.
    """
    data: dict[str, Any] = {
        "t": int(trx_id),
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if verify_url:
        data["u"] = str(verify_url)

    if extra:
        # Solo valores JSON-serializables
        data["x"] = extra

    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    secret = current_app.config.get("QR_SIGN_SECRET")
    if secret:
        data["sig"] = _sign_payload(payload, str(secret))
        payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    return payload


def _paste_logo(img, logo_path: str, scale: float = 0.22):
    """
    Inserta un logo centrado dentro del QR. Requiere Pillow.
    Si falla, continúa sin logo.
    """
    if Image is None:
        return img  # Pillow no disponible

    try:
        # Normaliza a absoluto
        if not os.path.isabs(logo_path):
            logo_path = os.path.join(getattr(current_app, "root_path", os.getcwd()), logo_path)
        if not os.path.exists(logo_path):
            return img

        logo = Image.open(logo_path).convert("RGBA")

        # Reescala logo
        w, h = img.size
        box_side = int(min(w, h) * max(0.1, min(scale, 0.35)))
        logo.thumbnail((box_side, box_side), Image.LANCZOS)

        # Pega centrado
        lw, lh = logo.size
        pos = ((w - lw) // 2, (h - lh) // 2)

        # Fondo blanco para mejorar contraste
        canvas = Image.new("RGBA", (lw + 8, lh + 8), (255, 255, 255, 230))
        img.paste(canvas, (pos[0] - 4, pos[1] - 4), canvas)
        img.paste(logo, pos, logo)
    except Exception:
        return img
    return img


# ========= API pública ========= #

def generar_qr(
    *,
    trx_id: int,
    payload: Optional[str] = None,
    verify_url: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
    filename: Optional[str] = None,
    # estilo/robustez
    error_correction: str = "M",
    box_size: int = 8,
    border: int = 3,
    # logo opcional
    logo_path: Optional[str] = None,
    logo_scale: float = 0.22,
) -> str:
    """
    Genera y guarda un QR en PNG. Devuelve la ruta ABSOLUTA del archivo.

    Estrategias de payload:
        - Si 'payload' se indica, se usa tal cual.
        - Si no, se construye uno JSON con trx_id, ts, y opcionalmente verify_url + extra.
          Si existe config['QR_SIGN_SECRET'], se añade firma HMAC en 'sig'.

    Parámetros:
        trx_id: ID de la transacción (para nombrar archivo y payload por defecto).
        payload: Texto completo a codificar en el QR (omite verify_url/extra).
        verify_url: URL de verificación (opcional si no pasás 'payload').
        extra: Dict con metadatos no sensibles (p.ej. {'pelicula':'X','email':'y@z'}).
        filename: Nombre de archivo (por defecto: 'qr_trx_{trx_id}.png').
        error_correction: 'L'|'M'|'Q'|'H' (por defecto 'M').
        box_size: Tamaño de cada módulo QR (default 8).
        border: Borde en módulos (default 3).
        logo_path: Ruta (relativa o absoluta) a un PNG/JPG usado como logo central (opcional).
        logo_scale: Proporción del logo respecto al lado del QR (0.10–0.35 recomendado).

    Config esperada en Flask:
        QR_DIR: carpeta de salida (relativa a raíz de app o absoluta). Default: 'static/qr'
        QR_SIGN_SECRET: (opcional) secreto para firmar payloads construidos

    Raises:
        QRGenerationError: ante problemas al generar o guardar el PNG.
    """
    try:
        # Directorio de destino
        out_dir_cfg = current_app.config.get("QR_DIR", "static/qr")
        out_dir = _abs_storage_dir(out_dir_cfg)
        _ensure_dir(out_dir)

        # Nombre de archivo
        if not filename:
            filename = f"qr_trx_{trx_id}.png"
        out_path = os.path.join(out_dir, filename)

        # Payload final
        data_str = payload if payload is not None else _build_payload(
            trx_id=trx_id, verify_url=verify_url, extra=extra
        )

        # Construcción del QR
        qr = qrcode.QRCode(
            version=None,  # auto
            error_correction=_map_ec(error_correction),
            box_size=int(box_size),
            border=int(border),
        )
        qr.add_data(data_str)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

        # Logo opcional
        if logo_path:
            img = _paste_logo(img, logo_path=logo_path, scale=logo_scale)

        # Guardar PNG
        img.save(out_path, format="PNG", optimize=True)

        return out_path

    except Exception as exc:  # pragma: no cover
        raise QRGenerationError(f"No se pudo generar el QR (trx_id={trx_id}): {exc}") from exc
