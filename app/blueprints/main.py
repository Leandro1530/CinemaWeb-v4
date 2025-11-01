# app/blueprints/main.py
# -*- coding: utf-8 -*-
"""
Blueprint 'main': pantallas de bienvenida y selección de sucursal (branch).

Requisitos:
- templates/bienvenida.html  (usa variables: branches, current_branch, current_branch_id)
- app/data/seed.py con la lista BRANCHES
"""

from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, session, request
from app.data.seed import BRANCHES

bp = Blueprint("main", __name__)


@bp.get("/")
def inicio():
    """
    Entrada raíz: redirige a la pantalla de bienvenida.
    """
    return redirect(url_for("main.bienvenida"))


@bp.get("/bienvenida")
def bienvenida():
    """
    Muestra la pantalla de bienvenida con el selector de sucursal.
    - branches: lista de sucursales disponibles
    - current_branch: sucursal actualmente seleccionada en sesión (si existe)
    - current_branch_id: id de la sucursal seleccionada (mismo string)
    """
    branches = [{"id": b, "nombre": b} for b in BRANCHES]
    current_id = session.get("branch")
    current_branch = next((b for b in branches if b["id"] == current_id), None)

    return render_template(
        "bienvenida.html",
        branches=branches,
        current_branch=current_branch,
        current_branch_id=current_id,
    )


@bp.post("/set-branch")
def set_branch():
    """
    Recibe el branch seleccionado desde un <form>:
      <select name="branch">...</select>
    Guarda la selección en sesión y redirige a la cartelera.
    """
    chosen = (request.form.get("branch") or "").strip()
    if chosen:
        session["branch"] = chosen
    # Nota: si no viene 'branch', simplemente vuelve a cartelera (o podrías volver a bienvenida)
    return redirect(url_for("venta.cartelera"))


@bp.post("/clear-branch")
def clear_branch():
    """
    Limpia la sucursal seleccionada de la sesión y vuelve a bienvenida.
    """
    session.pop("branch", None)
    return redirect(url_for("main.bienvenida"))
