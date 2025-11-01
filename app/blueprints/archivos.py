# app/blueprints/archivos.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from flask import Blueprint, current_app, send_from_directory, abort

bp = Blueprint("archivos", __name__)

def _abs_storage_dir(rel_or_abs: str) -> str:
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    base = getattr(current_app, "root_path", os.getcwd())
    return os.path.join(base, rel_or_abs)

@bp.get("/comprobante/<int:trx_id>/descargar")
def descargar_comprobante(trx_id: int):
    """
    Devuelve el PDF generado por services/pdfs.py
    Nombre por defecto: 'comprobante_trx_{trx_id}.pdf'
    """
    filename = f"comprobante_trx_{trx_id}.pdf"
    rel_dir = current_app.config.get("COMPROBANTES_DIR", "static/comprobantes")
    directory = _abs_storage_dir(rel_dir)
    file_path = os.path.join(directory, filename)

    if not os.path.exists(file_path):
        abort(404, description="Comprobante no encontrado")

    # Forzar descarga
    return send_from_directory(directory=directory, path=filename, as_attachment=True)
