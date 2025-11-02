#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para ejecutar migraciones de base de datos
"""

from app.db import get_conn

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
            
        conn.close()
            
    except Exception as e:
        print(f"❌ Error en migración trailer_url: {e}")

if __name__ == "__main__":
    print("🔄 Ejecutando migración para agregar trailer_url...")
    migrate_add_trailer_url()
    print("✅ Migración completada")