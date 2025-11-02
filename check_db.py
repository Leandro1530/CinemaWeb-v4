import sqlite3
import os

# Buscar el archivo de base de datos
db_files = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.db'):
            db_files.append(os.path.join(root, file))

print("Archivos de base de datos encontrados:")
for db_file in db_files:
    print(f"  - {db_file}")

# Si no hay archivos .db, intentar crear la estructura
if not db_files:
    print("No se encontraron archivos .db. Creando base de datos...")
    from app.db import get_conn
    try:
        conn = get_conn()
        # Verificar si la tabla funciones existe
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='funciones'")
        if cursor.fetchone():
            print("✅ Tabla funciones existe")
            # Verificar columnas
            cursor = conn.execute("PRAGMA table_info(funciones)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"Columnas actuales: {columns}")
            
            if 'trailer_url' not in columns:
                conn.execute('ALTER TABLE funciones ADD COLUMN trailer_url TEXT')
                conn.commit()
                print("✅ Columna trailer_url agregada")
            else:
                print("⏭️ Columna trailer_url ya existe")
        else:
            print("❌ Tabla funciones no existe")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")