# app/models.py
# -*- coding: utf-8 -*-
"""
Modelos de dominio (ligeros) basados en dataclasses.
No requieren SQLAlchemy. Incluyen helpers para mapping desde SQLite y para templates.

Contiene:
- Money helpers (centavos <-> float)
- Combo, Funcion, Movie, Selection (elecciones en el flujo)
- Transaction (mapea la tabla 'transacciones')
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, List, Mapping, Optional, Sequence


# ===================== Helpers de dinero ===================== #

def cents_to_float(cents: int | float | None) -> float:
    try:
        return round(float(cents or 0) / 100.0, 2)
    except Exception:
        return 0.0


def float_to_cents(amount: float | str | None) -> int:
    if amount is None:
        return 0
    try:
        if isinstance(amount, str):
            amount = amount.replace(".", "").replace(",", ".")
            return int(round(float(amount), 2) * 100)
        return int(round(float(amount), 2) * 100)
    except Exception:
        return 0


def format_currency(value: float | int) -> str:
    """
    Formatea $ con coma decimal estilo AR.
    """
    try:
        if isinstance(value, int):
            value = cents_to_float(value)
        return f"$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"$ {value}"


# ===================== Catálogo / flujo ===================== #

@dataclass(slots=True)
class Combo:
    id: int
    nombre: str
    descripcion: str = ""
    precio: float = 0.0  # en unidades monetarias

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "Combo":
        return cls(
            id=int(m.get("id", 0)),
            nombre=str(m.get("nombre", "")),
            descripcion=str(m.get("descripcion", "")),
            precio=float(m.get("precio", 0.0)),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["precio_fmt"] = format_currency(self.precio)
        return d


@dataclass(slots=True)
class Funcion:
    fecha: str
    hora: str
    sala: str

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "Funcion":
        return cls(
            fecha=str(m.get("fecha", "")),
            hora=str(m.get("hora", "")),
            sala=str(m.get("sala", "")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Movie:
    id: str
    titulo: str
    poster_url: str = ""
    sinopsis: str = ""
    duracion_min: int = 0
    clasificacion: str = ""
    genero: str = ""
    funciones: List[Funcion] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "Movie":
        funcs = [Funcion.from_mapping(f) for f in (m.get("funciones") or [])]
        return cls(
            id=str(m.get("id", "")),
            titulo=str(m.get("titulo", "")),
            poster_url=str(m.get("poster_url", "")),
            sinopsis=str(m.get("sinopsis", "")),
            duracion_min=int(m.get("duracion_min", 0) or 0),
            clasificacion=str(m.get("clasificacion", "")),
            genero=str(m.get("genero", "")),
            funciones=funcs,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["funciones"] = [f.to_dict() for f in self.funciones]
        return d


@dataclass(slots=True)
class Selection:
    """
    Elección actual del usuario: movie + función + asientos + combos.
    Se usa para renderizar confirmación y para emitir el comprobante.
    """
    movie_id: str
    titulo: str
    fecha: str
    hora: str
    sala: str
    poster_url: str | None = None
    asientos: List[str] = field(default_factory=list)
    combos: List[Combo] = field(default_factory=list)

    @classmethod
    def from_session(cls, seleccion: Mapping[str, Any], seats: Sequence[str], combos: Iterable[Mapping[str, Any]]) -> "Selection":
        return cls(
            movie_id=str(seleccion.get("id", "")),
            titulo=str(seleccion.get("titulo", "")),
            fecha=str(seleccion.get("fecha", "")),
            hora=str(seleccion.get("hora", "")),
            sala=str(seleccion.get("sala", "")),
            poster_url=seleccion.get("poster_url"),
            asientos=[str(s).upper().strip() for s in (seats or []) if str(s).strip()],
            combos=[Combo.from_mapping(c) for c in (combos or [])],
        )

    @property
    def total_combos(self) -> float:
        return round(sum(c.precio for c in self.combos), 2)

    @property
    def total_combos_fmt(self) -> str:
        return format_currency(self.total_combos)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["combos"] = [c.to_dict() for c in self.combos]
        d["total_combos"] = self.total_combos
        d["total_combos_fmt"] = self.total_combos_fmt
        return d


# ===================== Persistencia: transacciones ===================== #

@dataclass(slots=True)
class Transaction:
    """
    Representa una fila de la tabla 'transacciones'.
    Guarda montos en centavos (monto_cents) para precisión;
    provee helpers para formato y conversión.
    """
    id: int
    usuario_email: str
    monto_cents: int
    brand: str | None = None
    last4: str | None = None
    exp_mes: int | None = None
    exp_anio: int | None = None
    estado: str | None = None
    auth_code: str | None = None
    created_at: str | None = None  # ISO string 'YYYY-MM-DD HH:MM:SS'

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Transaction":
        """
        Mapea una fila sqlite3.Row -> Transaction.
        """
        return cls(
            id=int(row["id"]),
            usuario_email=str(row["usuario_email"]),
            monto_cents=int(row["monto_cents"]),
            brand=(row["brand"] if row["brand"] is not None else None),
            last4=(row["last4"] if row["last4"] is not None else None),
            exp_mes=int(row["exp_mes"]) if row["exp_mes"] is not None else None,
            exp_anio=int(row["exp_anio"]) if row["exp_anio"] is not None else None,
            estado=(row["estado"] if row["estado"] is not None else None),
            auth_code=(row["auth_code"] if row["auth_code"] is not None else None),
            created_at=(row["created_at"] if row["created_at"] is not None else None),
        )

    @property
    def monto(self) -> float:
        return cents_to_float(self.monto_cents)

    @property
    def monto_fmt(self) -> str:
        return format_currency(self.monto)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["monto"] = self.monto
        d["monto_fmt"] = self.monto_fmt
        return d
