# cinema/services/pdfs.py
# -*- coding: utf-8 -*-
"""
Generación de comprobantes en PDF para tickets/entradas.

Dependencias:
  - fpdf2
  - Flask (solo para current_app)

Uso típico (desde un blueprint):
    from cinema.services.pdfs import generar_comprobante_pdf
    pdf_path = generar_comprobante_pdf(
        trx_id=trx_id,
        cliente=nombre_cliente,
        email=email,
        pelicula=pelicula_titulo,
        fecha_funcion="2025-09-15",
        hora_funcion="20:30",
        sala="Sala 1",
        asientos=["B5", "B6"],
        combos=[{"nombre": "Combo Pop + Gaseosa", "cantidad": 1, "precio": 4500.00}],
        total=12900.00,
        sucursal=session.get("branch") or current_app.config.get("DEFAULT_BRANCH"),
        qr_path=qr_path,  # opcional; si no existe, se omite
    )
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Iterable, Mapping, Optional, Sequence, Union

from fpdf import FPDF
from fpdf.errors import FPDFException
from flask import current_app


class PDFGenerationError(Exception):
    """Error al generar el PDF del comprobante."""


Number = Union[int, float]
ComboDict = Mapping[str, Union[str, Number]]
StrSeq = Sequence[str]


# ---------------------------------------------------------------------
# Utils de FS / formateo
# ---------------------------------------------------------------------
def _ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _abs_storage_dir(rel_or_abs: str) -> str:
    # Si es relativo, referencia a la carpeta raíz de la app Flask
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    base = getattr(current_app, "root_path", os.getcwd())
    return os.path.join(base, rel_or_abs)


def _format_currency(value: Number) -> str:
    try:
        return f"$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"$ {value}"


def _normalize_asientos(asientos: Union[str, Iterable[str], None]) -> list[str]:
    if asientos is None:
        return []
    if isinstance(asientos, str):
        # Permitir "A1, A2, A3"
        parts = [x.strip() for x in asientos.split(",") if x.strip()]
        return parts
    return [str(x).strip() for x in asientos if str(x).strip()]


def _normalize_combos(combos: Optional[Iterable[ComboDict]]) -> list[dict]:
    norm: list[dict] = []
    if not combos:
        return norm
    for c in combos:
        nombre = str(c.get("nombre", "")).strip()
        try:
            cantidad = int(c.get("cantidad", 0))
        except Exception:
            cantidad = 0
        try:
            precio = float(c.get("precio", 0.0))
        except Exception:
            precio = 0.0
        if nombre and cantidad > 0:
            norm.append({"nombre": nombre, "cantidad": cantidad, "precio": precio})
    return norm


# ---------------------------------------------------------------------
# Helpers robustos para layout con FPDF (evita "Not enough horizontal space")
# ---------------------------------------------------------------------
def _avail_width(pdf: FPDF) -> float:
    """Ancho útil total (página - márgenes)."""
    return float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin)


def _remain_width(pdf: FPDF) -> float:
    """Ancho restante desde X actual hasta margen derecho."""
    return float(pdf.w) - float(pdf.r_margin) - float(pdf.get_x())


def _ensure_w(pdf: FPDF, requested: float | None, min_w: float = 20.0) -> float:
    """Asegura un ancho positivo y razonable para poder renderizar texto."""
    if requested is None or requested <= 0:
        w = _remain_width(pdf)
    else:
        w = requested
    return max(min_w, float(w))


def _soft_wrap_tokens(text: str, hard_every: int = 28) -> str:
    """
    Inserta espacios suaves dentro de tokens sin espacios (emails larguísimos, hashes, etc.)
    para permitir corte de línea. No rompe palabras normales.
    """
    def breaker(m):
        s = m.group(0)
        return " ".join(s[i:i + hard_every] for i in range(0, len(s), hard_every))

    # tokens ≥ hard_every sin separadores “amables”
    return re.sub(r"[^\s\-_/.:@]{%d,}" % hard_every, breaker, text or "-")


def _safe_multicell(pdf: FPDF, w: float | None, h: float, txt: str, align: str = "L"):
    """
    multi_cell tolerante: garantiza ancho válido, reintenta con font-size menor si es necesario.
    """
    txt = _soft_wrap_tokens(str(txt))
    width = _ensure_w(pdf, w)
    family = pdf.font_family or "Helvetica"
    style = pdf.font_style or ""
    size = pdf.font_size_pt or 11

    try:
        pdf.multi_cell(width, h, txt, align=align)
        return
    except FPDFException:
        # Reintento: mover a nueva línea, resetear X y usar todo el ancho útil
        pdf.ln(h)
        pdf.set_x(pdf.l_margin)
        width = _ensure_w(pdf, _avail_width(pdf))
        try:
            pdf.multi_cell(width, h, txt, align=align)
            return
        except FPDFException:
            # último intento: bajar fuente 1pt
            try:
                pdf.set_font(family, style, max(8, size - 1))
                pdf.multi_cell(width, h, txt, align=align)
            finally:
                pdf.set_font(family, style, size)


# ---------------------------------------------------------------------
# Bloques de UI PDF
# ---------------------------------------------------------------------
def _kv(pdf: FPDF, k: str, v: str, w_key: float = 40.0, line_h: float = 6.0) -> None:
    """
    Imprime una línea Clave:Valor (clave en bold) de forma segura:
    - Asegura espacio horizontal; si no alcanza, baja de línea y resetea X.
    - El valor usa multi_cell “tolerante” para evitar excepciones.
    """
    # Si el espacio restante no alcanza para la clave + mínimo valor, forzar salto
    min_val_w = 24.0
    need = w_key + min_val_w
    if _remain_width(pdf) < need:
        pdf.ln(line_h)
        pdf.set_x(pdf.l_margin)

    family = pdf.font_family or "Helvetica"
    size = pdf.font_size_pt or 11

    # Clave
    pdf.set_font(family, "B", 9)  # Fuente más pequeña
    pdf.cell(35.0, 4.5, k, 0, 0)

    # Valor
    pdf.set_font(family, "", 9)  # Fuente más pequeña
    v_w = _avail_width(pdf) - 35.0
    v_w = _ensure_w(pdf, v_w, min_w=20.0)
    _safe_multicell(pdf, v_w, 4.5, v, align="L")
    # multi_cell deja X en margen izquierdo; no agregamos ln extra.


def _subtitle(pdf: FPDF, text: str) -> None:
    pdf.ln(2)  # Espaciado reducido
    family = pdf.font_family or "Helvetica"
    size = pdf.font_size_pt or 11
    
    # Caja más pequeña
    pdf.set_fill_color(245, 245, 245)
    pdf.set_text_color(60, 60, 60)
    pdf.rect(pdf.l_margin, pdf.get_y(), _avail_width(pdf), 6, 'F')
    
    pdf.set_font(family, "B", 10)  # Fuente más pequeña
    pdf.cell(0, 6, f"  {text}", 0, 1)
    pdf.set_font(family, "", size)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)  # Espaciado inferior reducido


def _draw_header(pdf: FPDF, sucursal: str, verif_code: str) -> None:
    family = pdf.font_family or "Helvetica"
    
    # Banner principal más compacto
    pdf.set_fill_color(41, 128, 185)
    pdf.set_text_color(255, 255, 255)
    pdf.rect(pdf.l_margin, pdf.get_y(), _avail_width(pdf), 15, 'F')
    
    # Título principal más pequeño
    pdf.set_font(family, "B", 16)
    pdf.cell(0, 6, "", 0, 1)  # Espaciado superior reducido
    pdf.cell(0, 6, "CINEMA3D", 0, 1, "C")
    pdf.set_font(family, "", 10)
    pdf.cell(0, 4, "COMPROBANTE DE COMPRA", 0, 1, "C")
    
    # Resetear colores
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    
    # Información de sucursal y código en la misma línea
    pdf.set_font(family, "", 9)
    pdf.cell(0, 4, f"Sucursal: {sucursal} | Codigo: {verif_code}", 0, 1, "C")
    pdf.ln(2)


# ---------------------------------------------------------------------
# Generación principal
# ---------------------------------------------------------------------
def generar_comprobante_pdf(
    *,
    trx_id: int,
    cliente: str,
    email: str,
    pelicula: str,
    fecha_funcion: str,
    hora_funcion: str,
    sala: str,
    asientos: Union[str, Iterable[str]],
    combos: Optional[Iterable[ComboDict]],
    total: Number,
    sucursal: str,
    qr_path: Optional[str] = None,
    filename: Optional[str] = None,
    genero: Optional[str] = None,
    duracion: Optional[str] = None,
    director: Optional[str] = None,
    clasificacion: Optional[str] = None,
) -> str:
    """
    Genera un PDF de comprobante mejorado y devuelve la ruta absoluta del archivo.
    
    Args:
        genero: Género de la película (opcional)
        duracion: Duración de la película (opcional)
        director: Director de la película (opcional)
        clasificacion: Clasificación por edad (opcional)

    Raises:
        PDFGenerationError: si ocurre un error al crear o guardar el PDF.
    """
    try:
        # Directorio de salida desde config (con fallback)
        out_dir_cfg = current_app.config.get("COMPROBANTES_DIR", "static/comprobantes")
        out_dir = _abs_storage_dir(out_dir_cfg)
        _ensure_dir(out_dir)

        # Datos normalizados
        asientos_list = _normalize_asientos(asientos)
        combos_list = _normalize_combos(combos)
        fecha_emision = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        verif_code = uuid.uuid4().hex[:12].upper()

        # Nombre de archivo
        if not filename:
            filename = f"comprobante_trx_{trx_id}.pdf"
        pdf_path = os.path.join(out_dir, filename)

        # === Comienzo del PDF ===
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        # Márgenes más pequeños para aprovechar mejor el espacio
        pdf.set_left_margin(10)
        pdf.set_right_margin(10)
        pdf.set_top_margin(10)
        pdf.set_auto_page_break(auto=False)  # Desactivar salto automático
        pdf.add_page()
        pdf.set_font("Helvetica", "", 9)  # Fuente base más pequeña

        # Encabezado
        _draw_header(pdf, sucursal=sucursal or "-", verif_code=verif_code)

        # Bloque de datos de operación
        _subtitle(pdf, "Datos de la operacion")
        _kv(pdf, "ID Transaccion:", f"#{trx_id}")
        _kv(pdf, "Cliente:", cliente or "-")
        _kv(pdf, "Email:", email or "-")
        _kv(pdf, "Fecha emision:", fecha_emision)

        # Bloque de función
        _subtitle(pdf, "Detalles de la funcion")
        _kv(pdf, "Pelicula:", pelicula or "-")
        
        # Información adicional de la película si está disponible
        if genero:
            _kv(pdf, "Genero:", genero)
        if duracion:
            _kv(pdf, "Duracion:", duracion)
        if director:
            _kv(pdf, "Director:", director)
        if clasificacion:
            _kv(pdf, "Clasificacion:", clasificacion)
            
        _kv(pdf, "Fecha funcion:", fecha_funcion or "-")
        _kv(pdf, "Hora:", hora_funcion or "-")
        _kv(pdf, "Sala:", sala or "-")
        
        # Asientos con formato especial
        if asientos_list:
            asientos_str = ", ".join(asientos_list)
            _kv(pdf, "Asientos:", f"Butacas: {asientos_str}")
        else:
            _kv(pdf, "Asientos:", "-")

        # Bloque de combos (si hay)
        if combos_list:
            _subtitle(pdf, "Combos incluidos")
            family = pdf.font_family or "Helvetica"
            size = 8  # Fuente más pequeña para la tabla

            # Cabecera con fondo
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font(family, "B", size)
            pdf.cell(80, 6, "Descripcion", 1, 0, "L", True)
            pdf.cell(15, 6, "Cant.", 1, 0, "C", True)
            pdf.cell(25, 6, "Precio Unit.", 1, 0, "R", True)
            pdf.cell(0, 6, "Subtotal", 1, 1, "R", True)
            
            pdf.set_fill_color(255, 255, 255)
            pdf.set_font(family, "", size)

            combo_total = 0.0
            for i, c in enumerate(combos_list):
                nombre = c["nombre"]
                cantidad = int(c["cantidad"])
                precio = float(c["precio"])
                subtotal = cantidad * precio
                combo_total += subtotal

                # Alternar colores de fila
                fill = i % 2 == 0
                if fill:
                    pdf.set_fill_color(250, 250, 250)
                else:
                    pdf.set_fill_color(255, 255, 255)

                pdf.cell(80, 5, nombre[:30], 1, 0, "L", fill)  # Filas más pequeñas
                pdf.cell(15, 5, str(cantidad), 1, 0, "C", fill)
                pdf.cell(25, 5, _format_currency(precio), 1, 0, "R", fill)
                pdf.cell(0, 5, _format_currency(subtotal), 1, 1, "R", fill)

            # Total de combos
            pdf.set_fill_color(220, 220, 220)
            pdf.set_font(family, "B", size)
            pdf.cell(120, 6, "SUBTOTAL COMBOS", 1, 0, "R", True)
            pdf.cell(0, 6, _format_currency(combo_total), 1, 1, "R", True)
            pdf.set_font(family, "", size)

        # Total destacado más compacto
        pdf.ln(3)
        
        # Caja con fondo para el total más pequeña
        pdf.set_fill_color(41, 128, 185)
        pdf.set_text_color(255, 255, 255)
        pdf.rect(pdf.l_margin, pdf.get_y(), _avail_width(pdf), 10, 'F')
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"TOTAL PAGADO: {_format_currency(total)}", 0, 1, "C")
        
        # Resetear colores
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        
        # Nota legal más compacta
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(90, 90, 90)
        _safe_multicell(
            pdf,
            0,
            4,
            "Este comprobante es valido como constancia de compra. "
            "Conservar para eventuales controles en la entrada del cine.",
        )
        pdf.set_text_color(0, 0, 0)

        # QR opcional
        if qr_path:
            try:
                abs_qr = qr_path
                if not os.path.isabs(abs_qr):
                    # Si viene relativo, resolver respecto a raíz de la app
                    abs_qr = os.path.join(getattr(current_app, "root_path", os.getcwd()), qr_path)
                if os.path.exists(abs_qr):
                    pdf.ln(3)
                    _subtitle(pdf, "Verificacion rapida (QR)")
                    # Inserta la imagen más pequeña
                    x = pdf.get_x()
                    y = pdf.get_y()
                    pdf.image(abs_qr, x=x, y=y, w=30, h=30)  # QR más pequeño
                    pdf.set_xy(x + 35, y + 3)
                    pdf.set_font("Helvetica", "", 8)
                    _safe_multicell(
                        pdf,
                        0,
                        4,
                        "Escanee el codigo para validar los datos del ticket "
                        "o acceder al digital en su cuenta (si corresponde).",
                    )
                    pdf.ln(25)
            except Exception:
                # No abortar por problemas de imagen; el ticket sigue siendo válido
                pass

        # Footer más compacto
        y_actual = pdf.get_y()
        if y_actual > 250:  # Si estamos muy abajo, mover arriba
            y_actual = 250
        
        pdf.set_y(y_actual + 5)
        
        # Línea separadora
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)
        
        # Información del footer más compacta
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(41, 128, 185)
        pdf.cell(0, 4, "Gracias por elegirnos!", 0, 1, "C")
        
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 4, "Cinema3D - Sistema de Venta de Entradas", 0, 1, "C")
        pdf.cell(0, 3, f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}", 0, 1, "C")
        
        pdf.set_text_color(0, 0, 0)

        # Guardar
        pdf.output(pdf_path)

        return pdf_path

    except Exception as exc:
        raise PDFGenerationError(f"No se pudo generar el PDF (trx_id={trx_id}): {exc}") from exc


def generar_reporte_ventas_pdf(
    *,
    fecha_inicio: str,
    fecha_fin: str,
    ventas_data: list,
    total_ventas: Number,
    total_entradas: int,
    sucursal: str,
    filename: Optional[str] = None,
) -> str:
    """
    Genera un PDF de reporte de ventas para administradores.
    
    Args:
        fecha_inicio: Fecha de inicio del reporte
        fecha_fin: Fecha de fin del reporte
        ventas_data: Lista de datos de ventas
        total_ventas: Total de ventas en el período
        total_entradas: Total de entradas vendidas
        sucursal: Nombre de la sucursal
        filename: Nombre del archivo (opcional)
    
    Returns:
        str: Ruta absoluta del archivo PDF generado
    """
    try:
        # Directorio de salida desde config
        out_dir_cfg = current_app.config.get("COMPROBANTES_DIR", "static/comprobantes")
        out_dir = _abs_storage_dir(out_dir_cfg)
        _ensure_dir(out_dir)

        # Nombre de archivo
        if not filename:
            fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reporte_ventas_{fecha_str}.pdf"
        pdf_path = os.path.join(out_dir, filename)

        # Crear PDF
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
        pdf.set_top_margin(15)
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "", 11)

        # Encabezado del reporte
        pdf.set_fill_color(41, 128, 185)
        pdf.set_text_color(255, 255, 255)
        pdf.rect(pdf.l_margin, pdf.get_y(), _avail_width(pdf), 20, 'F')
        
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 8, "", 0, 1)
        pdf.cell(0, 8, "REPORTE DE VENTAS", 0, 1, "C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 6, f"Del {fecha_inicio} al {fecha_fin}", 0, 1, "C")
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)

        # Resumen ejecutivo
        _subtitle(pdf, "Resumen Ejecutivo")
        _kv(pdf, "Sucursal:", sucursal)
        _kv(pdf, "Período:", f"{fecha_inicio} - {fecha_fin}")
        _kv(pdf, "Total Entradas Vendidas:", f"{total_entradas:,}")
        _kv(pdf, "Total Ingresos:", _format_currency(total_ventas))
        
        if total_entradas > 0:
            promedio_por_entrada = float(total_ventas) / total_entradas
            _kv(pdf, "Promedio por Entrada:", _format_currency(promedio_por_entrada))

        # Tabla de ventas detallada
        if ventas_data:
            _subtitle(pdf, "Detalle de Ventas")
            
            # Cabecera de tabla
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(20, 8, "Fecha", 1, 0, "C", True)
            pdf.cell(60, 8, "Película", 1, 0, "L", True)
            pdf.cell(25, 8, "Entradas", 1, 0, "C", True)
            pdf.cell(30, 8, "Combos", 1, 0, "R", True)
            pdf.cell(0, 8, "Total", 1, 1, "R", True)
            
            # Datos
            pdf.set_font("Helvetica", "", 9)
            for i, venta in enumerate(ventas_data):
                fill = i % 2 == 0
                if fill:
                    pdf.set_fill_color(250, 250, 250)
                else:
                    pdf.set_fill_color(255, 255, 255)
                
                pdf.cell(20, 6, venta.get('fecha', ''), 1, 0, "C", fill)
                pdf.cell(60, 6, venta.get('pelicula', '')[:25], 1, 0, "L", fill)
                pdf.cell(25, 6, str(venta.get('entradas', 0)), 1, 0, "C", fill)
                pdf.cell(30, 6, _format_currency(venta.get('combos', 0)), 1, 0, "R", fill)
                pdf.cell(0, 6, _format_currency(venta.get('total', 0)), 1, 1, "R", fill)

        # Footer del reporte
        pdf.set_y(-25)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(3)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        _safe_multicell(pdf, 0, 5, "Cinema3D · Reporte Generado Automáticamente", align="C")
        _safe_multicell(pdf, 0, 4, f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}", align="C")

        pdf.output(pdf_path)
        return pdf_path

    except Exception as exc:
        raise PDFGenerationError(f"No se pudo generar el reporte PDF: {exc}") from exc
