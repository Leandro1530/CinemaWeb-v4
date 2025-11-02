# app/db_migrations.py
# -*- coding: utf-8 -*-
"""
Migraciones de base de datos para soporte de MercadoPago
"""

import sqlite3
from flask import current_app
from app.db import get_conn, execute, executescript

def migrate_add_trailer_url():
    """
    Migración para agregar la columna trailer_url a la tabla funciones
    """
    try:
        conn = get_conn()
        
        # Verificar si la columna trailer_url ya existe
        cursor = conn.execute("PRAGMA table_info(funciones)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'trailer_url' not in columns:
            # Agregar la columna trailer_url
            conn.execute('ALTER TABLE funciones ADD COLUMN trailer_url TEXT')
            conn.commit()
            print("✅ Columna trailer_url agregada a la tabla funciones")
        else:
            print("⏭️ La columna trailer_url ya existe")
            
    except Exception as e:
        print(f"❌ Error en migración trailer_url: {e}")

def migrate_database():
    """
    Ejecuta todas las migraciones necesarias
    """
    print("🔄 Ejecutando migraciones de base de datos...")
    migrate_add_mercadopago_support()
    migrate_add_trailer_url()
    print("✅ Migraciones completadas")

def migrate_add_mercadopago_support():
    """
    Migración para agregar soporte completo de MercadoPago
    Agrega tabla de transacciones y funciones mejoradas
    """
    
    try:
        conn = get_conn()
        
        # Verificar si la tabla transacciones ya existe
        cur = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='transacciones'
        """)
        table_exists = cur.fetchone() is not None
        
        if table_exists:
            # La tabla existe, agregar columnas de MercadoPago una por una
            current_app.logger.info("📊 Tabla transacciones existe, agregando columnas MP...")
            
            # Lista de columnas que necesitamos agregar
            new_columns = [
                ("monto_cents", "INTEGER NOT NULL DEFAULT 0"),
                ("mp_preference_id", "TEXT"),
                ("mp_payment_id", "TEXT"), 
                ("mp_status", "TEXT"),
                ("mp_status_detail", "TEXT"),
                ("monto_mp", "DECIMAL(10,2)"),
                ("monto_neto_mp", "DECIMAL(10,2)"),
                ("external_reference", "TEXT"),
                ("funcion_id", "INTEGER"),
                ("pelicula", "TEXT"),
                ("fecha_funcion", "TEXT"),
                ("hora_funcion", "TEXT"),
                ("sala", "TEXT"),
                ("asientos_json", "TEXT"),
                ("combos_json", "TEXT"),
                ("notas", "TEXT"),
                ("ip_cliente", "TEXT"),
                ("user_agent", "TEXT"),
                ("fecha_actualizacion", "TIMESTAMP")
            ]
            
            for column_name, column_def in new_columns:
                try:
                    conn.execute(f"ALTER TABLE transacciones ADD COLUMN {column_name} {column_def}")
                    current_app.logger.info(f"✅ Columna {column_name} agregada")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        current_app.logger.info(f"⚡ Columna {column_name} ya existe")
                    else:
                        current_app.logger.warning(f"⚠️ Error agregando {column_name}: {str(e)}")
            
            # Migrar email_cliente -> usuario_email si es necesario
            try:
                cur = conn.execute("SELECT email_cliente FROM transacciones LIMIT 1")
                current_app.logger.info("🔄 Migrando email_cliente -> usuario_email")
                
                try:
                    conn.execute("ALTER TABLE transacciones ADD COLUMN usuario_email TEXT")
                except sqlite3.OperationalError:
                    pass
                
                conn.execute("UPDATE transacciones SET usuario_email = email_cliente WHERE usuario_email IS NULL")
                current_app.logger.info("✅ Migración email_cliente completada")
                
            except sqlite3.OperationalError:
                current_app.logger.info("⚡ Tabla ya usa usuario_email")
        
        else:
            # Crear tabla desde cero
            current_app.logger.info("🏗️ Creando tabla transacciones completa...")
            executescript("""
                CREATE TABLE IF NOT EXISTS transacciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_email TEXT NOT NULL,
                    monto_cents INTEGER NOT NULL DEFAULT 0,
                    total_pesos DECIMAL(10,2) NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
                    funcion_id INTEGER,
                    pelicula TEXT,
                    fecha_funcion TEXT,
                    hora_funcion TEXT,
                    sala TEXT,
                    asientos_json TEXT,
                    combos_json TEXT,
                    mp_preference_id TEXT,
                    mp_payment_id TEXT,
                    mp_status TEXT,
                    mp_status_detail TEXT,
                    monto_mp DECIMAL(10,2),
                    monto_neto_mp DECIMAL(10,2),
                    external_reference TEXT,
                    brand TEXT,
                    last4 TEXT,
                    exp_mes INTEGER,
                    exp_anio INTEGER,
                    auth_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion TIMESTAMP,
                    notas TEXT,
                    ip_cliente TEXT,
                    user_agent TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_transacciones_email ON transacciones(usuario_email);
                CREATE INDEX IF NOT EXISTS idx_transacciones_estado ON transacciones(estado);
                CREATE INDEX IF NOT EXISTS idx_transacciones_mp_payment ON transacciones(mp_payment_id);
                CREATE INDEX IF NOT EXISTS idx_transacciones_external_ref ON transacciones(external_reference);
            """)
        
        # Crear otras tablas necesarias
        try:
            executescript("""
                CREATE TABLE IF NOT EXISTS funciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pelicula_id TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    pelicula TEXT,  -- columna legacy por compatibilidad
                    fecha TEXT NOT NULL,
                    hora TEXT NOT NULL,
                    sala TEXT NOT NULL,
                    precio DECIMAL(10,2) NOT NULL DEFAULT 2500,
                    precio_entrada DECIMAL(10,2) NOT NULL DEFAULT 2500,  -- alias legacy
                    asientos_totales INTEGER DEFAULT 50,
                    asientos_disponibles INTEGER DEFAULT 50,
                    genero TEXT,
                    duracion INTEGER DEFAULT 120,
                    clasificacion TEXT DEFAULT '+13',
                    poster TEXT,
                    descripcion TEXT,
                    activo BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_funciones_fecha_hora ON funciones(fecha, hora);
                CREATE INDEX IF NOT EXISTS idx_funciones_pelicula ON funciones(pelicula);
                CREATE INDEX IF NOT EXISTS idx_funciones_pelicula_id ON funciones(pelicula_id);
                
                CREATE TABLE IF NOT EXISTS combos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    descripcion TEXT,
                    precio DECIMAL(10,2) NOT NULL,
                    activo BOOLEAN DEFAULT 1,
                    imagen_url TEXT,
                    categoria TEXT DEFAULT 'combo',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_combos_activo ON combos(activo);
            """)
            current_app.logger.info("✅ Tablas auxiliares creadas")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error creando tablas auxiliares: {str(e)}")
        
        # Insertar datos de ejemplo
        try:
            insert_sample_data()
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error insertando datos de ejemplo: {str(e)}")
        
        current_app.logger.info("✅ Migración MercadoPago completada exitosamente")
        
    except Exception as e:
        current_app.logger.error(f"❌ Error en migración MercadoPago: {str(e)}")
        raise

def insert_sample_data():
    """Inserta datos de ejemplo si las tablas están vacías"""
    
    try:
        conn = get_conn()
        
        # Funciones de ejemplo
        try:
            cur = conn.execute("SELECT COUNT(*) as count FROM funciones")
            if cur.fetchone()["count"] == 0:
                current_app.logger.info("📝 Insertando funciones de ejemplo...")
                
                sample_funciones = [
                    ("Avengers: Endgame", "2025-10-15", "20:00", "Sala 1", 2500.00),
                    ("Avengers: Endgame", "2025-10-16", "18:00", "Sala 1", 2500.00),
                    ("Spider-Man: No Way Home", "2025-10-15", "22:00", "Sala 2", 2800.00),
                    ("Avatar: The Way of Water", "2025-10-16", "19:30", "Sala 3", 3000.00),
                ]
                
                for pelicula, fecha, hora, sala, precio in sample_funciones:
                    execute(
                        "INSERT INTO funciones (pelicula, fecha, hora, sala, precio_entrada) VALUES (?, ?, ?, ?, ?)",
                        [pelicula, fecha, hora, sala, precio],
                        commit=False
                    )
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error insertando funciones: {str(e)}")
        
        # Combos de ejemplo  
        try:
            cur = conn.execute("SELECT COUNT(*) as count FROM combos")
            if cur.fetchone()["count"] == 0:
                current_app.logger.info("🍿 Insertando combos de ejemplo...")
                
                sample_combos = [
                    ("Combo Clásico", "Pochoclos medianos + Gaseosa 500ml", 1500.00),
                    ("Combo Familiar", "Pochoclos grandes + 2 Gaseosas 500ml", 2200.00),
                    ("Combo Dulce", "Nachos + Gaseosa 500ml + Dulces", 1800.00),
                    ("Solo Pochoclos", "Pochoclos grandes", 800.00),
                    ("Solo Gaseosa", "Gaseosa 500ml", 600.00),
                ]
                
                for nombre, descripcion, precio in sample_combos:
                    execute(
                        "INSERT INTO combos (nombre, descripcion, precio) VALUES (?, ?, ?)",
                        [nombre, descripcion, precio],
                        commit=False
                    )
        except Exception as e:
            current_app.logger.warning(f"⚠️ Error insertando combos: {str(e)}")
        
        conn.commit()
        current_app.logger.info("✅ Datos de ejemplo insertados")
        
    except Exception as e:
        current_app.logger.error(f"❌ Error en insert_sample_data: {str(e)}")

def check_migration_needed():
    """Verifica si se necesita ejecutar la migración"""
    try:
        conn = get_conn()
        
        # Verificar si existe la tabla transacciones
        cur = conn.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='transacciones'
        """)
        
        result = cur.fetchone()
        if not result:
            return True  # Tabla no existe
        
        # Verificar si tiene las columnas de MercadoPago
        table_sql = result["sql"]
        mp_columns = ["mp_preference_id", "mp_payment_id", "external_reference"]
        
        for col in mp_columns:
            if col not in table_sql:
                return True  # Falta alguna columna de MP
        
        return False  # No necesita migración
        
    except Exception as e:
        current_app.logger.error(f"Error verificando migración: {str(e)}")
        return True  # En caso de error, ejecutar migración


def load_seed_data():
    """Carga los datos del archivo seed.py en la base de datos"""
    from app.data.seed import MOVIES, COMBOS_CATALOG
    
    try:
        conn = get_conn()
        current_app.logger.info("🌱 Cargando datos semilla...")
        
        # Limpiar datos existentes
        execute("DELETE FROM funciones", commit=False)
        execute("DELETE FROM combos", commit=False)
        
        # Cargar películas y funciones
        for movie in MOVIES:
            movie_id = movie['id']
            titulo = movie['titulo']
            genero = movie.get('genero', '')
            duracion = movie.get('duracion_min', 120)
            clasificacion = movie.get('clasificacion', '+13')
            poster = movie.get('poster_url', '')
            descripcion = movie.get('sinopsis', '')
            
            # Insertar funciones de la película
            for funcion in movie.get('funciones', []):
                execute("""
                    INSERT INTO funciones (
                        pelicula_id, titulo, fecha, hora, sala, precio, 
                        genero, duracion, clasificacion, poster, descripcion,
                        asientos_disponibles
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    movie_id, titulo, funcion['fecha'], funcion['hora'], 
                    funcion['sala'], 2500, genero, duracion, clasificacion,
                    poster, descripcion, 50
                ], commit=False)
        
        # Cargar combos
        for combo in COMBOS_CATALOG:
            execute("""
                INSERT INTO combos (id, nombre, descripcion, precio)
                VALUES (?, ?, ?, ?)
            """, [
                combo['id'], combo['nombre'], combo['descripcion'], combo['precio']
            ], commit=False)
        
        # Confirmar todos los cambios
        conn.commit()
        current_app.logger.info("✅ Datos semilla cargados correctamente")
        
    except Exception as e:
        current_app.logger.error(f"❌ Error cargando datos semilla: {str(e)}")
        raise


def migrate_add_password_reset_support():
    """
    Migración para agregar soporte de recuperación de contraseñas
    Agrega tabla password_reset_tokens
    """
    
    try:
        conn = get_conn()
        
        # Verificar si la tabla password_reset_tokens ya existe
        cur = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='password_reset_tokens'
        """)
        table_exists = cur.fetchone() is not None
        
        if table_exists:
            current_app.logger.info("📊 Tabla password_reset_tokens ya existe")
            return
        
        current_app.logger.info("📊 Creando tabla password_reset_tokens...")
        
        # Crear tabla de tokens de recuperación
        execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                token      TEXT    NOT NULL,
                expires_at INTEGER NOT NULL,
                used       INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """, commit=False)
        
        # Crear índices
        execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token)
        """, commit=False)
        
        execute("""
            CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id)
        """, commit=False)
        
        # Confirmar cambios
        conn.commit()
        current_app.logger.info("✅ Tabla password_reset_tokens creada correctamente")
        
    except Exception as e:
        current_app.logger.error(f"❌ Error creando tabla password_reset_tokens: {str(e)}")
        raise