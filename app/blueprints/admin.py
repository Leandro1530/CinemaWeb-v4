# app/blueprints/admin.py
# -*- coding: utf-8 -*-
"""
Blueprint 'admin': Funciones administrativas para gestión del sistema.

Rutas administrativas protegidas que solo pueden acceder usuarios con rol 'admin':
- Gestión de funciones de cine (CRUD)
- Gestión de usuarios (CRUD)
- Visualización de transacciones
- Configuración del sistema
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app.blueprints.auth import require_admin, current_user
import app.db as db_mod
from werkzeug.security import generate_password_hash

bp = Blueprint("admin", __name__, url_prefix="/admin")

# =======================================================================
# Gestión de Funciones
# =======================================================================

@bp.route("/funciones")
@require_admin()
def funciones():
    """Lista todas las funciones disponibles para administrar"""
    try:
        # Obtener todas las funciones desde la base de datos
        from datetime import datetime, date
        
        funciones_db = db_mod.query_all("""
            SELECT id, pelicula_id, titulo, genero, duracion, clasificacion,
                   poster, descripcion, fecha, hora, sala, precio, asientos_disponibles
            FROM funciones
            ORDER BY fecha, hora
        """)
        
        funciones_data = []
        for funcion in funciones_db:
            # Determinar el estado de la función
            fecha_funcion = datetime.strptime(funcion['fecha'], '%Y-%m-%d').date()
            hoy = date.today()
            
            if fecha_funcion < hoy:
                status = 'past'
            elif fecha_funcion == hoy:
                status = 'active'
            else:
                status = 'upcoming'
            
            funciones_data.append({
                'id': funcion['id'],  # Usar el ID numérico de la base de datos
                'titulo': funcion['titulo'],
                'genero': funcion['genero'],
                'duracion': funcion['duracion'],
                'fecha': funcion['fecha'],
                'hora': funcion['hora'],
                'sala': funcion['sala'],
                'precio': funcion['precio'],
                'poster': funcion['poster'],
                'status': status
            })
        
        # Calcular estadísticas
        total = len(funciones_data)
        activas = len([f for f in funciones_data if f['status'] == 'active'])
        proximas = len([f for f in funciones_data if f['status'] == 'upcoming'])
        pasadas = len([f for f in funciones_data if f['status'] == 'past'])
        
        stats = {
            'total': total,
            'activas': activas,
            'proximas': proximas,
            'pasadas': pasadas
        }
        
        return render_template("admin/funciones.html", funciones=funciones_data, stats=stats)
    except Exception as e:
        flash(f"Error al cargar funciones: {str(e)}", "error")
        return redirect(url_for('main.bienvenida'))

@bp.route("/funciones/nueva", methods=["GET", "POST"])
@require_admin()
def nueva_funcion():
    """Crear una nueva función"""
    if request.method == "GET":
        return render_template("admin/funcion_form.html", funcion=None)
    
    # POST - crear función
    try:
        # Obtener datos del formulario
        titulo = request.form.get('titulo')
        genero = request.form.get('genero')
        duracion = request.form.get('duracion')
        fecha = request.form.get('fecha')
        hora = request.form.get('hora')
        sala = request.form.get('sala', 'Sala 1')
        precio = request.form.get('precio', 5000)
        poster = request.form.get('poster', '')
        descripcion = request.form.get('descripcion', '')
        
        # Generar un ID de película único
        pelicula_id = f"m_{titulo.lower().replace(' ', '_')}"
        
        # Insertar la nueva función en la base de datos
        db_mod.execute("""
            INSERT INTO funciones (
                pelicula_id, titulo, genero, duracion, clasificacion,
                poster, descripcion, fecha, hora, sala, precio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [pelicula_id, titulo, genero, duracion, 'PG-13', poster, descripcion, fecha, hora, sala, precio])
        
        flash("Función creada exitosamente", "success")
        return redirect(url_for('admin.funciones'))
        
    except Exception as e:
        flash(f"Error al crear función: {str(e)}", "error")
        return redirect(url_for('admin.funciones'))

@bp.route("/funciones/editar/<int:funcion_id>", methods=["GET", "POST"])
@require_admin()
def editar_funcion(funcion_id):
    """Editar una función existente"""
    try:
        # Buscar la función en la base de datos
        funcion = db_mod.query_one("""
            SELECT id, pelicula_id, titulo, genero, duracion, clasificacion,
                   poster, descripcion, fecha, hora, sala, precio
            FROM funciones WHERE id = ?
        """, [funcion_id])
        
        if not funcion:
            flash("Función no encontrada", "error")
            return redirect(url_for('admin.funciones'))
        
        if request.method == "POST":
            # Obtener datos del formulario
            titulo = request.form.get('titulo')
            genero = request.form.get('genero')
            duracion = request.form.get('duracion')
            fecha = request.form.get('fecha')
            hora = request.form.get('hora')
            sala = request.form.get('sala')
            precio = request.form.get('precio')
            poster = request.form.get('poster')
            descripcion = request.form.get('descripcion')
            
            # Actualizar la función en la base de datos
            db_mod.execute("""
                UPDATE funciones SET 
                    titulo = ?, genero = ?, duracion = ?, fecha = ?, 
                    hora = ?, sala = ?, precio = ?, poster = ?, descripcion = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, [titulo, genero, duracion, fecha, hora, sala, precio, poster, descripcion, funcion_id])
            
            flash("Función actualizada exitosamente", "success")
            return redirect(url_for('admin.funciones'))
        
        return render_template("admin/funcion_form.html", funcion=funcion)
        
    except Exception as e:
        flash(f"Error al editar función: {str(e)}", "error")
        return redirect(url_for('admin.funciones'))

@bp.route("/funciones/eliminar/<int:funcion_id>", methods=["POST"])
@require_admin()
def eliminar_funcion(funcion_id):
    """Eliminar una función"""
    try:
        # Primero verificar que la función existe
        funcion_existe = db_mod.query_one(
            "SELECT id FROM funciones WHERE id = ?", 
            [funcion_id]
        )
        
        if not funcion_existe:
            flash("Función no encontrada", "error")
            return redirect(url_for('admin.funciones'))
        
        # Eliminar función de la base de datos
        db_mod.execute(
            "DELETE FROM funciones WHERE id = ?", 
            [funcion_id]
        )
        
        flash("Función eliminada exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar función: {str(e)}", "error")
    
    return redirect(url_for('admin.funciones'))

# =======================================================================
# Gestión de Usuarios
# =======================================================================

@bp.route("/usuarios")
@require_admin()
def usuarios():
    """Lista todos los usuarios para administrar"""
    try:
        usuarios_data = db_mod.query_all("""
            SELECT id, nombre, apellido, email, nro_documento, rol, 
                   ciudad, provincia, telefono, 
                   datetime('now') as created_at
            FROM usuarios 
            ORDER BY rol DESC, email
        """)
        
        return render_template("admin/usuarios.html", usuarios=usuarios_data)
        
    except Exception as e:
        flash(f"Error al cargar usuarios: {str(e)}", "error")
        return redirect(url_for('main.bienvenida'))

@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@require_admin()
def nuevo_usuario():
    """Crear un nuevo usuario"""
    if request.method == "GET":
        return render_template("admin/usuario_form.html", usuario=None)
    
    # POST - crear usuario
    try:
        data = {
            'nombre': request.form.get('nombre').strip(),
            'apellido': request.form.get('apellido').strip(),
            'tipo_documento': request.form.get('tipo_documento', 'DNI'),
            'nro_documento': request.form.get('nro_documento').strip(),
            'email': request.form.get('email').strip() or None,
            'contrasena_hash': generate_password_hash(request.form.get('contrasena')),
            'rol': request.form.get('rol', 'usuario'),
            'telefono': request.form.get('telefono').strip() or None,
            'ciudad': request.form.get('ciudad').strip() or None,
            'provincia': request.form.get('provincia').strip() or None,
            'direccion': request.form.get('direccion').strip() or None,
            'codigo_postal': request.form.get('codigo_postal').strip() or None
        }
        
        user_id = db_mod.upsert_usuario(**data)
        
        # Actualizar el rol si es diferente de 'usuario'
        if data['rol'] != 'usuario':
            db_mod.execute("UPDATE usuarios SET rol = ? WHERE id = ?", [data['rol'], user_id], commit=True)
        
        flash("Usuario creado exitosamente", "success")
        return redirect(url_for('admin.usuarios'))
        
    except Exception as e:
        flash(f"Error al crear usuario: {str(e)}", "error")
        return render_template("admin/usuario_form.html", usuario=None)

@bp.route("/usuarios/editar/<int:user_id>", methods=["GET", "POST"])
@require_admin()
def editar_usuario(user_id):
    """Editar un usuario existente"""
    usuario = db_mod.query_one("SELECT * FROM usuarios WHERE id = ?", [user_id])
    
    if not usuario:
        flash("Usuario no encontrado", "error")
        return redirect(url_for('admin.usuarios'))
    
    if request.method == "GET":
        return render_template("admin/usuario_form.html", usuario=usuario)
    
    # POST - actualizar usuario
    try:
        # Actualizar datos básicos
        db_mod.execute("""
            UPDATE usuarios 
            SET nombre=?, apellido=?, email=?, telefono=?, ciudad=?, 
                provincia=?, direccion=?, codigo_postal=?, rol=?
            WHERE id=?
        """, [
            request.form.get('nombre').strip(),
            request.form.get('apellido').strip(),
            request.form.get('email').strip() or None,
            request.form.get('telefono').strip() or None,
            request.form.get('ciudad').strip() or None,
            request.form.get('provincia').strip() or None,
            request.form.get('direccion').strip() or None,
            request.form.get('codigo_postal').strip() or None,
            request.form.get('rol', 'usuario'),
            user_id
        ], commit=True)
        
        # Si hay nueva contraseña, actualizarla
        nueva_contrasena = request.form.get('nueva_contrasena')
        if nueva_contrasena:
            password_hash = generate_password_hash(nueva_contrasena)
            db_mod.execute("UPDATE usuarios SET contrasena = ? WHERE id = ?", 
                         [password_hash, user_id], commit=True)
        
        flash("Usuario actualizado exitosamente", "success")
        return redirect(url_for('admin.usuarios'))
        
    except Exception as e:
        flash(f"Error al actualizar usuario: {str(e)}", "error")
        return render_template("admin/usuario_form.html", usuario=usuario)

@bp.route("/usuarios/eliminar/<int:user_id>", methods=["POST"])
@require_admin()
def eliminar_usuario(user_id):
    """Eliminar un usuario"""
    try:
        # No permitir que el admin se elimine a sí mismo
        if current_user()['id'] == user_id:
            flash("No puedes eliminar tu propio usuario", "error")
            return redirect(url_for('admin.usuarios'))
        
        # Verificar si el usuario tiene transacciones
        transacciones = db_mod.query_one("SELECT COUNT(*) as count FROM transacciones WHERE usuario_email = (SELECT email FROM usuarios WHERE id = ?)", [user_id])
        
        if transacciones and transacciones['count'] > 0:
            flash("No se puede eliminar el usuario porque tiene transacciones asociadas", "error")
            return redirect(url_for('admin.usuarios'))
        
        # Eliminar usuario
        db_mod.execute("DELETE FROM usuarios WHERE id = ?", [user_id], commit=True)
        flash("Usuario eliminado exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar usuario: {str(e)}", "error")
    
    return redirect(url_for('admin.usuarios'))

# =======================================================================
# Dashboard administrativo
# =======================================================================

@bp.route("/")
@require_admin()
def dashboard():
    """Panel de control administrativo"""
    try:
        # Estadísticas básicas
        stats = {
            'total_usuarios': db_mod.query_one("SELECT COUNT(*) as count FROM usuarios")['count'],
            'total_transacciones': db_mod.query_one("SELECT COUNT(*) as count FROM transacciones")['count'],
            'total_funciones': db_mod.query_one("SELECT COUNT(*) as count FROM funciones")['count'],
            'ingresos_total': db_mod.query_one("SELECT COALESCE(SUM(monto_cents), 0) as total FROM transacciones")['total'] / 100
        }
        
        # Últimas transacciones
        ultimas_transacciones = db_mod.query_all("""
            SELECT id, usuario_email, monto_cents, created_at
            FROM transacciones 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        return render_template("admin/dashboard.html", stats=stats, transacciones=ultimas_transacciones)
        
    except Exception as e:
        flash(f"Error al cargar dashboard: {str(e)}", "error")
        return redirect(url_for('main.bienvenida'))