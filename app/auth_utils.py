# app/auth_utils.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import wraps
from flask import session, redirect, url_for, request, flash

def login_required(view):
    """
    Protege rutas: redirige a /login si no hay usuario en sesión.
    Uso:
        from app.auth_utils import login_required
        @bp.get("/area-privada")
        @login_required
        def privada(): ...
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Necesitás iniciar sesión para continuar.", "warning")
            return redirect(url_for("auth.login", next=request.full_path or request.path))
        return view(*args, **kwargs)
    return wrapped
